# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## Commands

### Setup
```bash
python -m venv venv
# Windows: .\venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

### Scrape free posts
```bash
python substack_scraper.py --url https://example.substack.com
python substack_scraper.py --url https://example.substack.com --number 10
python substack_scraper.py --url https://example.substack.com/p/single-post
```

### Scrape premium posts (requires Chrome or Edge)
First edit `config.py` with your Substack email/password, then:
```bash
# First run — login manually
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile
# Subsequent runs — reuse saved session
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile --skip-login
```

### Image downloading and MDX output
```bash
python substack_scraper.py --url https://example.substack.com --images
python substack_scraper.py --url https://example.substack.com --frontmatter mdx
```

### Run tests
```bash
pytest tests/ -v
pytest tests/test_substack_scraper.py::test_resolve_image_url_extracts_original_url -v
```

## Architecture

### Entry Point and CLI

The entire application lives in a single file: `substack_scraper.py` (~1500 lines). The `main()` function (line 1420) parses CLI arguments via `argparse` (`parse_args()`, line 1320) and instantiates either `SubstackScraper` (free) or `PremiumSubstackScraper` (premium), then calls `scrape_posts()`.

If no `--url` is provided, the script falls back to the hardcoded constants at the top of the file: `BASE_SUBSTACK_URL`, `NUM_POSTS_TO_SCRAPE`, and `USE_PREMIUM`.

### Scraper Class Hierarchy

```
BaseSubstackScraper (ABC, line 730)
├── SubstackScraper (line 1121)        # Free content via requests
└── PremiumSubstackScraper (line 1168) # Premium via Selenium browser automation
```

**`BaseSubstackScraper`** contains all shared logic:
- URL discovery: fetches post URLs from `sitemap.xml` (fallback: `feed.xml`), filters out `/about`, `/archive`, `/podcast` URLs
- HTML → Markdown conversion via `html2text`
- Post metadata extraction from `<script type="application/ld+json">` (title, date, author, cover image) and like-count scraping
- File I/O: saving `.md` and `.html` files, skipping existing files
- JSON metadata accumulation: `save_essays_data_to_json()` writes to `data/<author>.json`
- HTML author page generation: `generate_html_file()` at module level (line 151) populates `author_template.html` with JSON data

**`SubstackScraper.get_url_soup()`** (line 1134): Uses `requests.get()`, detects paywalled posts (`h2.paywall-title`) and rate limiting (`body > pre` with "too many requests"), retries with exponential backoff + jitter up to 5 attempts.

**`PremiumSubstackScraper`** (line 1168): Initializes a Selenium WebDriver before calling `super().__init__()` because URL fetching happens in the parent constructor. After instantiation, `login()` navigates to `https://substack.com/sign-in`, clicks "sign in with password", fills credentials from `config.py`, submits, and waits 30 seconds for completion. `get_url_soup()` uses `driver.get()` + `WebDriverWait` (20s timeout waiting for content/paywall/error markers), then parses with BeautifulSoup.

### BrowserManager (line 180)

A utility class handling WebDriver lifecycle with a four-strategy fallback:

1. **Explicit path**: user-provided `--chrome-driver-path` or `--edge-driver-path`
2. **Direct download**: `download_driver_with_requests()` fetches the correct chromedriver/msedgedriver from official CDNs (Chrome for Testing or Edge WebDriver) into `~/.substack_exporter/drivers/`, caching by major browser version
3. **webdriver_manager**: Python package fallback
4. **Selenium Manager**: last resort auto-management

Browser version detection uses PowerShell on Windows, `--version` on Linux. Driver-browser compatibility checked by comparing major version numbers. Persistent profiles (`--persistent-profile`) are stored in `~/.substack_exporter/<browser>_profile/`, preserving login cookies across runs so `--skip-login` can work.

### Image Downloading Pipeline (`--images`)

When the `--images` flag is set, `scrape_posts()` calls `process_markdown_images()` (line 126) which:
1. Resolves Substack CDN URLs (`https://substackcdn.com/image/fetch/...`) back to original URLs via `resolve_image_url()` (line 47)
2. Creates directory: `substack_images/<author>/<post_slug>/`
3. Downloads each image with `download_image()` (line 104) using `requests.get(stream=True)`
4. Rewrites markdown image references from CDN URLs to relative local paths

`count_images_in_markdown()` (line 62) provides the total for the progress bar after cleaning linked images via `clean_linked_images()` which converts `[![alt](img)](link)` to `![alt](img)`.

### Frontmatter Formats

`combine_metadata_and_content()` (line 890) supports two modes:
- **`legacy`** (default): `# Title\n\n## Subtitle\n\n**Date**\n\n**Likes:** N\n\n`
- **`mdx`**: YAML frontmatter `---\ntitle: "..."\nsubtitle: "..."\ndate: "YYYY-MM-DD"\nauthor: "..."\nimage: "..."\n---\n\n`

### HTML Generation & Browsing

Two separate HTML outputs:

1. **Per-post HTML** (`save_to_html_file`, line 847): Converts markdown to HTML via `markdown.markdown()` with `extra` extension, wraps in a template referencing `assets/css/essay-styles.css` via relative path.

2. **Author index page** (`generate_html_file`, line 151): Reads `data/<author>.json`, embeds it as inline JSON in `author_template.html`, writes to `substack_html_pages/<author>.html`. The JavaScript in `assets/js/populate-essays.js` renders the article list with sort-by-date and sort-by-likes toggles plus MD/HTML format switching.

### Data Flow Summary

```
CLI args (or hardcoded constants)
  → Scraper.__init__()
    → get_all_post_urls() → sitemap.xml → feed.xml
  → scrape_posts()
    → for each URL:
      → get_url_soup()        [requests or Selenium]
      → extract_post_data()   [BeautifulSoup + ld+json]
      → combine_metadata_and_content()
      → [optionally] process_markdown_images()
      → save_to_file()        [.md]
      → save_to_html_file()   [.html]
      → accumulate essays_data list
    → save_essays_data_to_json()  [data/<author>.json]
    → generate_html_file()        [substack_html_pages/<author>.html]
```

### Runtime Directory Layout

All output directories are created automatically:
- `substack_md_files/<author>/` — Markdown posts (named by URL slug)
- `substack_html_pages/<author>/` — Per-post HTML + author index page
- `data/<author>.json` — Post metadata for the author page
- `substack_images/<author>/<slug>/` — Downloaded images (if `--images`)

### Configuration

`config.py` holds `EMAIL` and `PASSWORD` — only used by `PremiumSubstackScraper.login()`. This file is gitignored so credentials are never committed. The `.gitignore` also excludes `__pycache__/`, `venv/`, `.idea/`, `.vscode/`, and all generated output directories (only `README.md` placeholders are kept in `data/` and `substack_html_pages/`).

### Key Dependencies

- `requests` + `BeautifulSoup` — free content fetching and parsing
- `selenium` + `webdriver_manager` — premium content browser automation
- `html2text` — HTML to Markdown conversion
- `markdown` — Markdown to HTML for per-post pages
- `tqdm` — progress bars throughout scraping and image downloading
- `pytest` — test framework

### Rate Limiting & Resilience

Both scrapers have exponential backoff with jitter: `base = 2^attempt`, `delay = base ± 20%`. The free scraper detects "too many requests" via `<body><pre>` in raw HTTP responses; the premium scraper detects it via Selenium page source. Existing files on disk are skipped so interrupted runs can be safely resumed.
