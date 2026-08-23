#!/usr/bin/env python3
"""
Web-based UI for Substack Exporter.
Provides a browser interface to configure and run the Substack scraper.
"""

import os
import sys
import json
import uuid
import shutil
import secrets
import threading
import subprocess
from datetime import datetime, timezone
from time import sleep, time

from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, abort, Response, session

# Selenium imports for login functionality
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Import BrowserManager from the scraper (safe — no side effects)
from substack_scraper import BrowserManager

# Try to import credentials; if missing, manual login will be used
try:
    from config import EMAIL, PASSWORD
except ImportError:
    EMAIL, PASSWORD = '', ''

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

# --- Auth ---
# Local-only token gate: closes the "any co-resident process or open browser
# tab can blind-fetch every route" hole that loopback binding alone doesn't
# cover. Set SUBSTACK_EXPORTER_TOKEN to pin it; otherwise a fresh token is
# generated per run and printed to the console.
AUTH_TOKEN = os.environ.get('SUBSTACK_EXPORTER_TOKEN') or secrets.token_urlsafe(24)


@app.before_request
def _require_token():
    if session.get('authed'):
        return None
    if secrets.compare_digest(request.args.get('token', ''), AUTH_TOKEN):
        session['authed'] = True
        return None
    abort(401, description='Missing or invalid token. Open the URL printed at startup.')


def _is_safe_path_component(name):
    """Reject empty/'.'/'..' segments and path separators in a single path component."""
    if name in ('', '.', '..'):
        return False
    if os.sep in name or (os.altsep and os.altsep in name):
        return False
    return True


def _safe_join(base_dir, *parts):
    """Join parts onto base_dir and resolve; return None if the result escapes base_dir."""
    base_dir = os.path.realpath(base_dir)
    target = os.path.realpath(os.path.join(base_dir, *parts))
    if os.path.commonpath([base_dir, target]) != base_dir:
        return None
    return target

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MD_DIR = os.path.join(BASE_DIR, 'substack_md_files')
HTML_DIR = os.path.join(BASE_DIR, 'substack_html_pages')
DATA_DIR = os.path.join(BASE_DIR, 'data')
IMAGE_DIR = os.path.join(BASE_DIR, 'substack_images')
VIDEO_DIR = os.path.join(BASE_DIR, 'substack_videos')
SCRAPER_SCRIPT = os.path.join(BASE_DIR, 'substack_scraper.py')

# --- Job Management ---
JOBS = {}
JOBS_LOCK = threading.Lock()


def _get_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)


def _update_job(job_id, **kwargs):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(kwargs)


def _create_job():
    job_id = str(uuid.uuid4())[:8]
    with JOBS_LOCK:
        JOBS[job_id] = {
            'id': job_id,
            'status': 'pending',
            'progress': [],
            'result': None,
            'error': None,
            'created_at': datetime.now().isoformat(),
            'completed_at': None,
        }
    return job_id


def _scan_new_results():
    """Scan data/ for JSON exports and return basic info."""
    results = []
    if os.path.exists(DATA_DIR):
        for fname in sorted(os.listdir(DATA_DIR)):
            if fname.endswith('.json'):
                fpath = os.path.join(DATA_DIR, fname)
                try:
                    mtime = os.path.getmtime(fpath)
                    with open(fpath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    author = fname.replace('.json', '')
                    count = len(data) if isinstance(data, list) else 1
                    results.append({
                        'author': author,
                        'count': count,
                        'json_file': fname,
                        'updated': datetime.fromtimestamp(mtime).isoformat(),
                    })
                except Exception:
                    pass
    return results


def run_scrape_job(job_id, params):
    """Run the scraper as a subprocess, streaming progress back."""
    job = _get_job(job_id)
    if not job:
        return

    _update_job(job_id, status='running')

    try:
        cmd = [sys.executable, SCRAPER_SCRIPT, '--url', params['url']]

        if params.get('number') and params['number'] > 0:
            cmd.extend(['--number', str(params['number'])])

        if params.get('premium'):
            cmd.append('--premium')
            cmd.append('--headless')
            cmd.append('--persistent-profile')
            cmd.append('--skip-login')
            if params.get('browser'):
                cmd.extend(['--browser', params['browser']])

        if params.get('images'):
            cmd.append('--images')

        if params.get('videos'):
            cmd.append('--videos')

        if params.get('frontmatter') == 'mdx':
            cmd.extend(['--frontmatter', 'mdx'])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=BASE_DIR,
        )

        # Stream output line by line
        for line in process.stdout:
            line = line.strip()
            if line:
                with JOBS_LOCK:
                    if job_id in JOBS:
                        JOBS[job_id]['progress'].append(line)

        process.wait()

        if process.returncode == 0:
            result = _scan_new_results()
            _update_job(job_id, status='completed', result=result,
                         completed_at=datetime.now().isoformat())
        else:
            _update_job(
                job_id, status='failed',
                error=f'Scraper exited with code {process.returncode}',
                completed_at=datetime.now().isoformat(),
            )

    except Exception as e:
        _update_job(job_id, status='failed', error=str(e),
                     completed_at=datetime.now().isoformat())


def list_all_exports():
    """Return all existing exports with file availability info."""
    exports = []
    if os.path.exists(DATA_DIR):
        for fname in sorted(os.listdir(DATA_DIR)):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(DATA_DIR, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                posts = data if isinstance(data, list) else []
                if not posts:
                    # Empty JSON — remove it and skip display
                    os.remove(fpath)
                    continue
                author = fname.replace('.json', '')
                exports.append({
                    'author': author,
                    'count': len(posts),
                    'json_file': fname,
                    'html_page': (
                        f'{author}.html'
                        if os.path.exists(os.path.join(HTML_DIR, f'{author}.html'))
                        else None
                    ),
                    'md_dir': (
                        author
                        if os.path.exists(os.path.join(MD_DIR, author))
                        else None
                    ),
                    'has_images': os.path.isdir(os.path.join(IMAGE_DIR, author)),
                    'has_videos': os.path.isdir(os.path.join(VIDEO_DIR, author)),
                    'posts': posts[:5],  # first 5 for preview
                })
            except Exception:
                pass

    # Clean up empty / orphan directories
    _cleanup_orphan_dirs(MD_DIR, exports)
    _cleanup_orphan_dirs(HTML_DIR, exports)

    return sorted(exports, key=lambda x: x['author'])


def _cleanup_orphan_dirs(base_dir, exports):
    """Remove author directories that are empty or have no valid export data."""
    if not os.path.exists(base_dir):
        return
    valid_authors = {e['author'] for e in exports}
    for entry in os.listdir(base_dir):
        entry_path = os.path.join(base_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        if entry not in valid_authors:
            # Orphan directory — no corresponding JSON data, remove entirely
            try:
                shutil.rmtree(entry_path)
            except OSError:
                pass
            continue
        # Valid author — remove if empty
        try:
            if not os.listdir(entry_path):
                os.rmdir(entry_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Login helpers (direct Selenium — opens visible browser)
# ---------------------------------------------------------------------------

def _try_click_any(driver, xpaths, description, timeout=10):
    """Try each XPath; click the first visible match. Return True on success."""
    end = time() + timeout
    while time() < end:
        for xpath in xpaths:
            try:
                el = driver.find_element(By.XPATH, xpath)
                if el.is_displayed():
                    el.click()
                    return True
            except Exception:
                continue
        sleep(0.5)
    print(f"[login] Could not find clickable: {description}")
    return False


def _find_input_any(driver, selectors):
    """Try multiple By-selector tuples and return the first match, or None."""
    for by, selector in selectors:
        try:
            el = driver.find_element(by, selector)
            if el and el.is_displayed():
                return el
        except Exception:
            continue
    return None


def _wait_for_login_page_leave(driver, timeout=180):
    """Wait until the browser leaves the sign-in page. Returns True on success."""
    end = time() + timeout
    while time() < end:
        sleep(1)
        current_url = driver.current_url
        if ('substack.com' in current_url
                and '/sign-in' not in current_url
                and '/login' not in current_url
                and current_url != 'about:blank'):
            return True
    return False


def run_login_job(job_id, browser):
    """
    Open a visible browser for manual Substack login.
    Try automated login first (if credentials exist in config.py),
    then fall back to manual login (user completes CAPTCHA etc.).
    Session is saved to persistent profile for subsequent --skip-login use.
    """
    _update_job(job_id, status='running')
    driver = None

    try:
        _update_job(job_id, progress=['Creating browser window for login...'])
        driver = BrowserManager.create_driver(
            browser=browser,
            headless=False,           # MUST be visible for user interaction
            use_persistent_profile=True,
        )

        _update_job(job_id, progress=['Navigating to Substack sign-in...'])
        driver.get('https://substack.com/sign-in')
        sleep(3)

        # ---- Step 1: click "Sign in with password" ----
        signin_selectors = [
            "//a[contains(text(),'Sign in with password')]",
            "//a[contains(text(),'sign in with password')]",
            "//button[contains(text(),'Sign in with password')]",
            "//a[contains(@class,'login-option')]",
            "//a[@data-testid='login-with-password']",
            "//div[contains(@class,'login-option')]//a",
            "//*[contains(text(),'password') and contains(@class,'login')]",
        ]
        clicked = _try_click_any(driver, signin_selectors, "Sign in with password", timeout=10)
        if not clicked:
            _update_job(job_id, progress=[
                'Could not find "Sign in with password" button.',
                'Showing sign-in page — please log in manually in the browser.',
            ])
        else:
            sleep(2)

        # ---- Step 2: try automated credential fill ----
        if EMAIL and PASSWORD:
            _update_job(job_id, progress=['Attempting automated login with credentials from config.py...'])
            email_input = _find_input_any(driver, [
                (By.NAME, "email"),
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='email']"),
                (By.XPATH, "//input[@placeholder='email' or contains(@placeholder,'Email')]"),
            ])
            pwd_input = _find_input_any(driver, [
                (By.NAME, "password"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='password']"),
                (By.XPATH, "//input[@placeholder='password' or contains(@placeholder,'Password')]"),
            ])

            if email_input and pwd_input:
                email_input.clear()
                email_input.send_keys(EMAIL)
                pwd_input.clear()
                pwd_input.send_keys(PASSWORD)

                submit_selectors = [
                    "//button[contains(text(),'Sign in')]",
                    "//button[contains(text(),'Log in')]",
                    "//button[@type='submit']",
                    "//button[contains(@class,'submit')]",
                    "//*[@id='substack-login']//button",
                    "//form//button[last()]",
                ]
                if not _try_click_any(driver, submit_selectors, "submit button", timeout=5):
                    pwd_input.send_keys(Keys.RETURN)

                # Quick check if automated login worked
                _update_job(job_id, progress=['Automated login submitted. Waiting for result...'])
                if _wait_for_login_page_leave(driver, timeout=15):
                    _update_job(job_id, status='completed',
                                progress=['[OK] Automated login successful! Profile saved.'],
                                result={'logged_in': True, 'auto': True})
                    return
                else:
                    _update_job(job_id, progress=[
                        'Automated login may have failed (CAPTCHA or 2FA required).',
                        'Please complete the login manually in the browser window.',
                    ])
            else:
                _update_job(job_id, progress=[
                    'Could not locate email/password fields.',
                    'Please log in manually in the browser window.',
                ])
        else:
            _update_job(job_id, progress=[
                'No credentials found in config.py.',
                'Please log in manually in the browser window.',
            ])

        # ---- Step 3: manual login fallback ----
        _update_job(job_id, progress=['Waiting for manual login (3 minutes timeout)...'])
        if _wait_for_login_page_leave(driver, timeout=180):
            _update_job(job_id, status='completed',
                        progress=['[OK] Manual login detected! Profile saved.'],
                        result={'logged_in': True, 'auto': False})
        else:
            _update_job(job_id, status='failed',
                        error='Login timed out (3 minutes). Please try again.',
                        progress=['Login timed out. The browser window will close.'])

    except Exception as e:
        _update_job(job_id, status='failed', error=str(e),
                    progress=[f'Error: {e}'])
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Flask routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    exports = list_all_exports()
    return render_template('index.html', exports=exports)


@app.route('/favicon.ico')
def favicon():
    """Serve the project favicon."""
    return send_from_directory(BASE_DIR, 'favicon.ico')


@app.route('/api/scrape', methods=['POST'])
def api_scrape():
    data = request.get_json(silent=True)
    if not data or not data.get('url'):
        return jsonify({'error': 'URL is required'}), 400

    # One job at a time
    with JOBS_LOCK:
        for job in JOBS.values():
            if job['status'] in ('pending', 'running'):
                return jsonify({
                    'error': 'A job is already in progress',
                    'job_id': job['id'],
                }), 409

    job_id = _create_job()
    params = {
        'url': data['url'],
        'number': int(data.get('number', 0) or 0),
        'premium': bool(data.get('premium', False)),
        'images': bool(data.get('images', False)),
        'videos': bool(data.get('videos', False)),
        'frontmatter': data.get('frontmatter', 'legacy'),
        'browser': data.get('browser', 'chrome'),
    }

    t = threading.Thread(target=run_scrape_job, args=(job_id, params), daemon=True)
    t.start()

    return jsonify({'job_id': job_id, 'status': 'pending'})


@app.route('/api/jobs/<job_id>')
def api_job_status(job_id):
    job = _get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404

    # Clone to avoid mutation during serialization
    resp = dict(job)
    progress = resp.get('progress', [])
    if len(progress) > 300:
        resp['progress'] = progress[-300:]
    return jsonify(resp)


@app.route('/api/login', methods=['POST'])
def api_login():
    """Open a visible browser for manual Substack login. Saves persistent profile."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    # One job at a time
    with JOBS_LOCK:
        for job in JOBS.values():
            if job['status'] in ('pending', 'running'):
                return jsonify({
                    'error': 'A job is already in progress',
                    'job_id': job['id'],
                }), 409

    browser = data.get('browser', 'chrome')
    job_id = _create_job()
    JOBS[job_id]['type'] = 'login'

    t = threading.Thread(target=run_login_job, args=(job_id, browser), daemon=True)
    t.start()

    return jsonify({'job_id': job_id, 'status': 'pending'})


@app.route('/api/exports')
def api_exports():
    return jsonify(list_all_exports())


@app.route('/preview/<path:filename>')
def serve_preview(filename):
    """Serve generated HTML pages for in-browser preview."""
    return send_from_directory(HTML_DIR, filename)


@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve static assets (CSS, JS) used by generated author pages."""
    return send_from_directory(os.path.join(BASE_DIR, 'assets'), filename)


@app.route('/substack_html_pages/<path:filename>')
def serve_generated_html(filename):
    """Serve per-post generated HTML pages."""
    return send_from_directory(HTML_DIR, filename)


@app.route('/substack_md_files/<path:filename>')
def serve_generated_md(filename):
    """Serve per-post generated Markdown files."""
    return send_from_directory(MD_DIR, filename)


@app.route('/raw/<author>/<path:filename>')
def serve_raw(author, filename):
    """Serve raw markdown files."""
    if not _is_safe_path_component(author):
        abort(404)
    return send_from_directory(os.path.join(MD_DIR, author), filename)


@app.route('/substack_images/<path:filename>')
def serve_images(filename):
    """Serve downloaded images."""
    return send_from_directory(IMAGE_DIR, filename)


def _stream_file_range(filepath, start, length, chunk_size=64 * 1024):
    """Generator that yields byte chunks from a file range (streaming)."""
    with open(filepath, 'rb') as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            chunk = f.read(min(chunk_size, remaining))
            if not chunk:
                break
            yield chunk
            remaining -= len(chunk)


def _is_ts_file(filepath):
    """Check if a .mp4 file is actually a raw TS (Transport Stream) file."""
    try:
        with open(filepath, 'rb') as f:
            return f.read(1) == b'\x47'
    except OSError:
        return False


def _remux_ts_to_mp4(ts_path):
    """Remux a TS file to a proper MP4 (lossless, fast). Caches next to the original.
    Returns the path to the MP4 on success, or None if ffmpeg is unavailable/fails."""
    mp4_path = ts_path + '.remuxed.mp4'
    if os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0:
        return mp4_path

    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    try:
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', ts_path, '-c', 'copy', '-movflags', '+faststart', mp4_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        if result.returncode == 0 and os.path.isfile(mp4_path) and os.path.getsize(mp4_path) > 0:
            return mp4_path
    except Exception:
        pass
    return None


@app.route('/substack_videos/<path:filename>')
def serve_videos(filename):
    """Serve videos with explicit Range support for seeking/scrubbing."""
    filepath = _safe_join(VIDEO_DIR, filename)
    if filepath is None or not os.path.isfile(filepath):
        abort(404)

    # Detect TS files disguised as .mp4 → remux to proper MP4 on the fly
    if filepath.endswith('.mp4') and _is_ts_file(filepath):
        mp4 = _remux_ts_to_mp4(filepath)
        if mp4:
            filepath = mp4

    ext = os.path.splitext(filename)[1].lower()
    mime_map = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.mkv': 'video/x-matroska'}
    mimetype = mime_map.get(ext, 'video/mp4')
    file_size = os.path.getsize(filepath)

    range_header = request.headers.get('Range', None)

    if not range_header:
        # No Range header — return full file (initial playback)
        return send_file(filepath, mimetype=mimetype)

    # Parse Range: "bytes=start-end"
    try:
        raw = range_header.replace('bytes=', '').strip()
        start_str, end_str = raw.split('-')
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
    except (ValueError, AttributeError):
        return send_file(filepath, mimetype=mimetype)

    # Validate range
    if start >= file_size or end >= file_size or start > end:
        resp = Response('', status=416)
        resp.headers['Content-Range'] = f'bytes */{file_size}'
        return resp

    end = min(end, file_size - 1)
    length = end - start + 1

    resp = Response(
        _stream_file_range(filepath, start, length),
        status=206,
        mimetype=mimetype,
        direct_passthrough=True,
    )
    resp.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    resp.headers['Accept-Ranges'] = 'bytes'
    resp.headers['Content-Length'] = str(length)
    resp.headers['Cache-Control'] = 'no-cache'

    return resp


@app.route('/api/media/<author>')
def api_media(author):
    """List images and videos for an author."""
    if not _is_safe_path_component(author):
        abort(404)
    result = {'images': {}, 'videos': {}}

    # Scan images: substack_images/<author>/<slug>/*.png|*.jpg|*.jpeg|*.gif|*.webp
    img_author_dir = os.path.join(IMAGE_DIR, author)
    if os.path.isdir(img_author_dir):
        for slug in sorted(os.listdir(img_author_dir)):
            slug_dir = os.path.join(img_author_dir, slug)
            if os.path.isdir(slug_dir):
                files = sorted(f for f in os.listdir(slug_dir)
                               if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')))
                if files:
                    result['images'][slug] = files

    # Scan videos: substack_videos/<author>/<slug>/*.mp4|*.webm|*.mkv
    vid_author_dir = os.path.join(VIDEO_DIR, author)
    if os.path.isdir(vid_author_dir):
        for slug in sorted(os.listdir(vid_author_dir)):
            slug_dir = os.path.join(vid_author_dir, slug)
            if os.path.isdir(slug_dir):
                files = sorted(f for f in os.listdir(slug_dir)
                               if f.lower().endswith(('.mp4', '.webm', '.mkv')))
                if files:
                    result['videos'][slug] = files

    return jsonify(result)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print('Substack Exporter Web UI')
    print(f'Open http://127.0.0.1:5000/?token={AUTH_TOKEN} in your browser')
    debug = os.environ.get('SUBSTACK_EXPORTER_DEBUG') == '1'
    app.run(debug=debug, host='127.0.0.1', port=5000)
