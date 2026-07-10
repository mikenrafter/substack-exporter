# substack-exporter

substack-exporter 是一个 Python 工具，用于下载 Substack 上的免费和付费文章，并将其保存为 Markdown 和 HTML 文件。它还包含一个简洁的 HTML 界面，方便用户浏览和排序文章。只要您订阅了该 Substack，它就会保存付费内容。

## 功能

- 将 Substack 文章转换为 Markdown 文件
- 同时生成 HTML 文件，方便浏览器阅读
- 生成作者主页 HTML，可按日期/点赞数排序浏览
- 支持免费和付费内容（需订阅 + Selenium 登录）
- 支持抓取单篇文章 URL（如 `/p/my-post`）
- 支持 `--images` 参数下载文章中的图片到本地
- 支持 `--frontmatter mdx` 生成 YAML 前置元数据

## 项目结构

```
substack-exporter/
├── substack_scraper.py      # 主入口脚本（CLI）
├── web_server.py             # Web 界面后端（Flask）
├── templates/
│   └── index.html            # Web 界面页面
├── static/
│   ├── css/web-ui.css        # Web 界面样式
│   └── js/web-ui.js          # Web 界面逻辑 + 中英文 i18n
├── config.py                 # 付费用户登录凭据（需自行填写）
├── author_template.html      # 作者主页 HTML 模板
├── requirements.txt          # Python 依赖
├── assets/
│   ├── css/                  # 样式文件
│   ├── js/                   # 前端 JS（排序/切换）
│   └── images/               # 截图等资源
├── tests/
│   └── test_substack_scraper.py  # 单元测试
├── data/                     # 文章元数据 JSON（运行时生成）
├── substack_md_files/        # 下载的 Markdown 文件（运行时生成）
├── substack_html_pages/      # 浏览用的 HTML 页面（运行时生成）
└── substack_images/          # 下载的图片（运行时生成）
```

## 安装

```bash
# 克隆项目
git clone <your-repo-url>
cd substack-exporter

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate    # Windows
# source venv/bin/activate # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

## 配置付费账号

如果要抓取付费内容，编辑项目根目录下的 `config.py`：

```python
EMAIL = "your-email@domain.com"
PASSWORD = "your-password"
```

> 注意：`config.py` 已在 `.gitignore` 中，不会被提交到 Git。

## Web 界面（推荐）

项目提供了一个现代化 Web 操作界面，支持中英文切换，无需记忆命令行参数。

```bash
# 启动 Web 服务
python web_server.py
```

浏览器打开 `http://127.0.0.1:5000`，即可在页面上：
- 输入 Substack URL 并配置抓取选项
- 一键开始抓取，实时查看进度日志
- 浏览历史导出，点击预览文章主页
- 点击右上角 **中/EN** 切换语言

> Web 界面后台通过子进程调用 `substack_scraper.py`，所有输出目录和 CLI 版本完全一致。

---

## 命令行使用

### 1. 抓取免费文章（全部）

```bash
python substack_scraper.py --url https://opinionai.substack.com
```

### 2. 抓取指定数量的免费文章

```bash
python substack_scraper.py --url https://example.substack.com --number 10
```

### 3. 抓取单篇文章

```bash
python substack_scraper.py --url https://example.substack.com/p/my-post
python substack_scraper.py --url https://stevemagness.substack.com/p/the-world-cup-we-suck-at-spotting
```

### 4. 抓取付费文章（需要 Chrome 或 Edge 浏览器）

```bash
python substack_scraper.py --url https://example.substack.com --premium
```

### 5. 付费 + 持久化登录状态（推荐）

首次运行（会打开浏览器，手动完成登录/验证码）：
```bash
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile
```

后续运行（跳过登录，复用已保存的会话）：
```bash
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile --skip-login
```

### 6. 下载文章中的图片到本地

```bash
python substack_scraper.py --url https://example.substack.com --images
```

### 7. 生成 MDX 兼容的 YAML frontmatter

```bash
python substack_scraper.py --url https://example.substack.com --frontmatter mdx
```

### 8. 指定保存目录

```bash
python substack_scraper.py --url https://example.substack.com --directory ./my_md_files
```

## 输出说明

运行后会在以下目录生成内容：

| 目录 | 内容 |
|------|------|
| `substack_md_files/<作者名>/` | 每篇文章的 `.md` 文件 |
| `substack_html_pages/<作者名>/` | 每篇文章的 `.html` 文件和作者主页 |
| `data/<作者名>.json` | 文章元数据（标题、日期、点赞数等）|
| `substack_images/<作者名>/` | 下载的图片（需 `--images`）|

打开 `substack_html_pages/<作者名>.html` 即可在浏览器中按日期/点赞数排序浏览所有文章。

## 命令行参数速查

| 参数 | 说明 |
|------|------|
| `-u, --url` | Substack 网址 |
| `-d, --directory` | Markdown 保存目录（默认 `substack_md_files`）|
| `-n, --number` | 抓取文章数量（0=全部） |
| `-p, --premium` | 付费模式（启用 Selenium 登录） |
| `--browser` | 浏览器选择：`chrome`（默认）或 `edge` |
| `--headless` | 无头模式（可能触发验证码） |
| `--persistent-profile` | 持久化浏览器登录状态 |
| `--skip-login` | 跳过登录（配合 `--persistent-profile`） |
| `--images` | 下载图片到本地 |
| `--frontmatter` | `legacy`（默认）或 `mdx` |
| `--chrome-driver-path` | 手动指定 chromedriver 路径 |
| `--edge-driver-path` | 手动指定 msedgedriver 路径 |

## 运行测试

```bash
pytest tests/ -v
```

## 常见问题

**Q: 提示浏览器驱动错误？**
A: 脚本会自动检测浏览器版本并下载匹配的驱动到 `~/.substack_exporter/drivers/`。如果失败，可以手动下载驱动并用 `--chrome-driver-path` 指定路径。

**Q: 付费模式登录失败/出现验证码？**
A: 去掉 `--headless` 参数，加上 `--persistent-profile`，手动完成验证码后，下次用 `--skip-login` 跳过登录。

**Q: 出现 "too many requests"？**
A: 脚本有内置重试机制，会自动等待后重试。如果频繁出现，建议减少 `--number` 分批抓取。

## License

MIT License - 详见 [LICENSE](LICENSE)
