/* ================================================================
   Substack Exporter — Web UI  (JavaScript + i18n)
   ================================================================ */

// ---------------------------------------------------------------------------
// i18n — Chinese / English
// ---------------------------------------------------------------------------
const I18N = {
  zh: {
    appName: 'Substack 导出工具',
    github: 'GitHub',
    heroTitle: '将 Substack 文章导出为 Markdown',
    heroSub: '一键抓取免费或付费 Substack 文章，输出干净的 Markdown 和 HTML。',
    newExport: '新建导出',
    urlLabel: 'Substack 链接',
    numLabel: '文章数量',
    numHint: '0 = 全部',
    fmtLabel: 'Frontmatter 格式',
    fmtLegacy: 'Legacy（经典）',
    fmtMdx: 'MDX（YAML）',
    premium: '付费内容',
    images: '下载图片',
    premiumNote: '首次使用？先点「登录」打开浏览器完成登录，后续抓取自动复用登录态。',
    browserLabel: '浏览器',
    loginBtn: '登录 / 设置 Profile',
    loginRunning: '正在打开登录窗口…',
    loginDone: '登录成功！Profile 已保存，现在可以开始抓取付费内容了。',
    loginFailed: '登录失败',
    startBtn: '开始抓取',
    pastExports: '历史导出',
    noExports: '暂无导出记录，在上方开始你的第一次抓取吧！',
    statusRunning: '正在抓取…',
    statusCompleted: '抓取完成！',
    statusFailed: '抓取失败',
    viewPage: '查看主页',
    viewMd: '查看 Markdown',
    openFolder: '打开目录',
    preview: '预览',
    errorMsg: '出错了，请检查 URL 或稍后重试。',
    jobRunning: '已有任务正在执行，请等待完成。',
  },
  en: {
    appName: 'Substack Exporter',
    github: 'GitHub',
    heroTitle: 'Export Substack to Markdown',
    heroSub: 'Scrape free or premium Substack posts into clean Markdown &amp; HTML. One click, no hassle.',
    newExport: 'New Export',
    urlLabel: 'Substack URL',
    numLabel: 'Number of posts',
    numHint: '0 = all',
    fmtLabel: 'Frontmatter format',
    fmtLegacy: 'Legacy',
    fmtMdx: 'MDX (YAML)',
    premium: 'Premium content',
    images: 'Download images',
    premiumNote: 'First time? Click "Login" to open a browser and sign in. Subsequent runs reuse the saved session.',
    browserLabel: 'Browser',
    loginBtn: 'Login / Setup Profile',
    loginRunning: 'Opening login window…',
    loginDone: 'Login successful! Profile saved. You can now scrape premium content.',
    loginFailed: 'Login failed',
    startBtn: 'Start Scraping',
    pastExports: 'Past Exports',
    noExports: 'No exports yet. Start one above!',
    statusRunning: 'Scraping…',
    statusCompleted: 'Scraping complete!',
    statusFailed: 'Scraping failed',
    viewPage: 'View Page',
    viewMd: 'View Markdown',
    openFolder: 'Open Folder',
    preview: 'Preview',
    errorMsg: 'Something went wrong. Check the URL or try again later.',
    jobRunning: 'A job is already running. Please wait for it to finish.',
  },
};

let currentLang = localStorage.getItem('substackLang') || 'en';

function t(key) {
  return I18N[currentLang]?.[key] ?? I18N['en']?.[key] ?? key;
}

function applyLanguage() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      el.placeholder = t(key);
    } else {
      el.textContent = t(key);
    }
  });
  // HTML lang attr
  document.documentElement.lang = currentLang;
  // Update lang switch
  document.querySelectorAll('.lang-option').forEach(opt => {
    opt.classList.toggle('active', opt.dataset.lang === currentLang);
  });
  localStorage.setItem('substackLang', currentLang);
}

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const scrapeUrl     = $('#scrapeUrl');
const scrapeNumber  = $('#scrapeNumber');
const scrapeFmt     = $('#scrapeFrontmatter');
const scrapePremium = $('#scrapePremium');
const scrapeImages  = $('#scrapeImages');
const scrapeBrowser = $('#scrapeBrowser');
const startBtn      = $('#startBtn');
const statusArea    = $('#statusArea');
const statusInd     = $('#statusIndicator');
const statusText    = $('#statusText');
const progressLog   = $('#progressLog');
const resultArea    = $('#resultArea');
const exportsList   = $('#exportsList');
const exportCount   = $('#exportCount');
const premiumOpts   = $('#premiumOptions');
const toastCont     = $('#toastContainer');
const loginBtn      = $('#loginBtn');
const loginStatus   = $('#loginStatusArea');
const loginLog      = $('#loginProgressLog');

let pollTimer = null;
let currentJobId = null;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
function init() {
  applyLanguage();
  renderExports(INITIAL_EXPORTS);

  // Premium toggle
  scrapePremium.addEventListener('change', () => {
    premiumOpts.hidden = !scrapePremium.checked;
  });

  // Language switch
  $('#langToggle').addEventListener('click', () => {
    currentLang = currentLang === 'en' ? 'zh' : 'en';
    applyLanguage();
  });

  // Login button
  loginBtn.addEventListener('click', startLogin);

  // Start button
  startBtn.addEventListener('click', startScrape);
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------
function showToast(msg, type) {
  const el = document.createElement('div');
  el.className = `toast ${type || ''}`;
  el.textContent = msg;
  toastCont.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ---------------------------------------------------------------------------
// Start scraping
// ---------------------------------------------------------------------------
async function startScrape() {
  const url = scrapeUrl.value.trim();
  if (!url) {
    showToast(t('urlLabel') + ' ' + t('errorMsg'), 'error');
    return;
  }

  // Reset UI
  startBtn.disabled = true;
  startBtn.textContent = '…';
  statusArea.hidden = false;
  resultArea.hidden = true;
  progressLog.textContent = '';
  statusInd.className = 'status-indicator running';
  statusText.textContent = t('statusRunning');

  const payload = {
    url: url,
    number: parseInt(scrapeNumber.value, 10) || 0,
    premium: scrapePremium.checked,
    images: scrapeImages.checked,
    frontmatter: scrapeFmt.value,
    browser: scrapeBrowser.value,
  };

  try {
    const resp = await fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (resp.status === 409) {
      const data = await resp.json();
      showToast(t('jobRunning'), 'error');
      startBtn.disabled = false;
      startBtn.textContent = t('startBtn');
      statusArea.hidden = true;
      return;
    }

    if (!resp.ok) {
      const data = await resp.json();
      throw new Error(data.error || 'Unknown error');
    }

    const data = await resp.json();
    currentJobId = data.job_id;
    startPolling();

  } catch (err) {
    statusInd.className = 'status-indicator failed';
    statusText.textContent = t('statusFailed');
    progressLog.textContent = err.message;
    showToast(t('errorMsg'), 'error');
    startBtn.disabled = false;
    startBtn.textContent = t('startBtn');
  }
}

// ---------------------------------------------------------------------------
// Poll job status
// ---------------------------------------------------------------------------
function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollJob, 1500);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function pollJob() {
  if (!currentJobId) {
    stopPolling();
    return;
  }

  try {
    const resp = await fetch(`/api/jobs/${currentJobId}`);
    if (!resp.ok) throw new Error('Job fetch failed');
    const job = await resp.json();

    const isLogin = job.type === 'login';

    // Update progress log
    const logTarget = isLogin ? loginLog : progressLog;
    if (job.progress && job.progress.length > 0) {
      logTarget.textContent = job.progress.slice(-150).join('\n');
      logTarget.scrollTop = logTarget.scrollHeight;
    }

    if (job.status === 'completed') {
      stopPolling();
      if (isLogin) {
        loginBtn.disabled = false;
        loginBtn.textContent = t('loginBtn');
        showToast(t('loginDone'), 'success');
      } else {
        statusInd.className = 'status-indicator completed';
        statusText.textContent = t('statusCompleted');
        startBtn.disabled = false;
        startBtn.textContent = t('startBtn');
        showResults(job);
        refreshExports();
      }
    } else if (job.status === 'failed') {
      stopPolling();
      if (isLogin) {
        loginBtn.disabled = false;
        loginBtn.textContent = t('loginBtn');
        showToast(t('loginFailed') + ': ' + (job.error || ''), 'error');
      } else {
        statusInd.className = 'status-indicator failed';
        statusText.textContent = t('statusFailed');
        if (job.error) {
          progressLog.textContent += '\n\nERROR: ' + job.error;
        }
        showToast(t('errorMsg'), 'error');
        startBtn.disabled = false;
        startBtn.textContent = t('startBtn');
      }
    }
  } catch (err) {
    console.error('Poll error:', err);
  }
}

// ---------------------------------------------------------------------------
// Login flow
// ---------------------------------------------------------------------------
async function startLogin() {
  loginBtn.disabled = true;
  loginBtn.textContent = '…';
  loginStatus.hidden = false;
  loginLog.textContent = '';

  try {
    const resp = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ browser: scrapeBrowser.value }),
    });

    if (resp.status === 409) {
      showToast(t('jobRunning'), 'error');
      loginBtn.disabled = false;
      loginBtn.textContent = t('loginBtn');
      return;
    }

    if (!resp.ok) {
      const data = await resp.json();
      throw new Error(data.error || 'Unknown error');
    }

    const data = await resp.json();
    currentJobId = data.job_id;
    startPolling();

  } catch (err) {
    loginLog.textContent = err.message;
    showToast(t('errorMsg'), 'error');
    loginBtn.disabled = false;
    loginBtn.textContent = t('loginBtn');
  }
}

// ---------------------------------------------------------------------------
// Show results
// ---------------------------------------------------------------------------
function showResults(job) {
  resultArea.hidden = false;
  resultArea.innerHTML = '';

  const authors = job.result || [];
  if (authors.length === 0) {
    resultArea.innerHTML = `<div class="result-title">${t('statusCompleted')}</div>`;
    return;
  }

  const title = document.createElement('div');
  title.className = 'result-title';
  title.textContent = t('statusCompleted');
  resultArea.appendChild(title);

  const links = document.createElement('div');
  links.className = 'result-links';

  for (const exp of authors) {
    const a = document.createElement('a');
    a.className = 'result-link';
    a.href = `/preview/${exp.author}.html`;
    a.target = '_blank';
    a.textContent = `${exp.author} (${exp.count})`;
    links.appendChild(a);
  }

  resultArea.appendChild(links);
}

// ---------------------------------------------------------------------------
// Exports list
// ---------------------------------------------------------------------------
function renderExports(exports) {
  exportsList.innerHTML = '';
  exportCount.textContent = exports.length;

  if (!exports || exports.length === 0) {
    const div = document.createElement('div');
    div.className = 'empty-state';
    div.setAttribute('data-i18n', 'noExports');
    div.textContent = t('noExports');
    exportsList.appendChild(div);
    return;
  }

  for (const exp of exports) {
    const item = document.createElement('div');
    item.className = 'export-item';

    // Info
    const info = document.createElement('div');
    info.className = 'export-info';
    const name = document.createElement('div');
    name.className = 'export-author';
    name.textContent = exp.author;
    const count = document.createElement('div');
    count.className = 'export-count';
    count.textContent = `${exp.count} posts`;
    info.appendChild(name);
    info.appendChild(count);

    // Actions
    const actions = document.createElement('div');
    actions.className = 'export-actions';

    if (exp.html_page) {
      const viewBtn = document.createElement('a');
      viewBtn.className = 'btn btn-outline btn-sm';
      viewBtn.href = `/preview/${exp.html_page}`;
      viewBtn.target = '_blank';
      viewBtn.textContent = t('preview');
      actions.appendChild(viewBtn);
    }

    item.appendChild(info);
    item.appendChild(actions);
    exportsList.appendChild(item);
  }
}

async function refreshExports() {
  try {
    const resp = await fetch('/api/exports');
    if (resp.ok) {
      const data = await resp.json();
      renderExports(data);
    }
  } catch (err) {
    console.error('Refresh exports error:', err);
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', init);

/* Global initial data from server-side render */
const INITIAL_EXPORTS = window.INITIAL_EXPORTS || [];
