# substack-exporter

[English](./README_EN.md) | 中文

Substack 和微信公众号本质上很像，都是个人做自媒体的工具，只是 Substack 的用户和创作者以海外为主。substack-exporter 是一个 Python 工具，用于下载 Substack 上的免费和付费文章，并将其保存为 Markdown 和 HTML 文件。它还包含一个简洁的 Web 界面，方便用户浏览和排序文章。只要您订阅了该 Substack，它就会保存付费内容。

## 截图展示

|            Web 操作界面             | 文章列表页 | 文章详情页 |
|:-------------------------------:|:---:|:---:|
| ![Web 界面](screenshot/index.png) | ![文章列表](screenshot/article-list.png) | ![文章详情](screenshot/article-detail.png) |

| 图片浏览 | 视频浏览 |
|:---:|:---:|
| ![图片列表](screenshot/photo-list.png) | ![视频列表](screenshot/video-list.png) |

## 核心功能

### Web 操作界面

- 现代化 Web UI，支持中英文一键切换
- 输入 Substack URL 即可配置抓取选项，实时查看进度日志
- 历史导出管理：浏览文章主页、预览 Markdown、打开文件目录
- **图片 & 视频浏览器**：在线查看已下载的图片网格和视频播放器

### 命令行工具

- 将 Substack 文章转换为 Markdown + HTML 文件
- 生成作者主页 HTML（按日期 / 点赞数排序浏览）
- 支持免费和付费内容（需订阅 + Selenium 登录）
- 支持抓取单篇文章 URL（如 `/p/my-post`）

### 多媒体下载

- `--images` 下载文章中的图片到本地，自动改写引用路径
- `--videos` 下载文章中的视频（HLS 流，需付费模式），自动用 ffmpeg 转封装为 MP4
- Web 界面支持图片网格浏览和视频在线播放（支持拖拽进度条）

### 元数据格式

- 支持 Legacy 经典格式和 MDX（YAML frontmatter）两种输出
- 自动提取标题、日期、作者、封面图、点赞数等元数据

## 安装

```bash
# 克隆项目
git clone https://github.com/yourname/substack-exporter.git
cd substack-exporter

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\activate    # Windows
# source venv/bin/activate # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

> **视频下载需要 ffmpeg**。Windows 用户：`winget install ffmpeg`，或从 [ffmpeg.org](https://ffmpeg.org/download.html) 下载。

## 使用方式

### Web 界面（推荐）

```bash
python web_server.py
```

浏览器打开 `http://127.0.0.1:5000`，即可在页面上：

| 功能 | 说明 |
|------|------|
| 新建导出 | 输入 Substack URL，选择免费/付费、下载图片/视频、文章数量等 |
| 进度监控 | 实时查看抓取进度和日志 |
| 历史管理 | 查看已抓取的作者，预览文章主页、Markdown 文件 |
| 媒体浏览 | 点击「查看图片」「查看视频」在线浏览多媒体内容 |
| 付费登录 | 点击「登录」打开浏览器完成 Substack 登录，后续自动复用 |
| 语言切换 | 右上角 **中 / EN** 一键切换 |

> Web 界面后台通过子进程调用 `substack_scraper.py`，所有输出目录和 CLI 版本完全一致。

### 命令行

#### 免费文章

```bash
# 抓取全部免费文章
python substack_scraper.py --url https://example.substack.com

# 抓取指定数量
python substack_scraper.py --url https://example.substack.com --number 10

# 抓取单篇文章
python substack_scraper.py --url https://example.substack.com/p/my-post
```

#### 付费文章（需 Chrome 或 Edge）

首次运行（会打开浏览器手动完成登录 / 验证码）：

```bash
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile
```

后续运行（复用已保存的会话）：

```bash
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile --skip-login
```

#### 下载图片和视频

```bash
# 下载文章中的图片
python substack_scraper.py --url https://example.substack.com --images

# 下载视频（需付费模式 + ffmpeg）
python substack_scraper.py --url https://example.substack.com --premium --persistent-profile --skip-login --videos
```

#### 其他选项

```bash
# MDX 兼容的 YAML frontmatter
python substack_scraper.py --url https://example.substack.com --frontmatter mdx

# 指定保存目录
python substack_scraper.py --url https://example.substack.com --directory ./my_md_files
```

## 配置付费账号

如果要抓取付费内容，编辑项目根目录下的 `config.py`：

```python
EMAIL = "your-email@domain.com"
PASSWORD = "your-password"
```

> 注意：`config.py` 已在 `.gitignore` 中，不会被提交到 Git。Web 界面的「登录」按钮会自动打开浏览器完成验证码，配置文件仅作为命令行登录的凭据。

## 命令行参数速查

| 参数 | 说明 |
|------|------|
| `-u, --url` | Substack 网址 |
| `-d, --directory` | Markdown 保存目录（默认 `substack_md_files`） |
| `-n, --number` | 抓取文章数量（0=全部） |
| `-p, --premium` | 付费模式（启用 Selenium 登录） |
| `--browser` | 浏览器选择：`chrome`（默认）或 `edge` |
| `--headless` | 无头模式（可能触发验证码） |
| `--persistent-profile` | 持久化浏览器登录状态 |
| `--skip-login` | 跳过登录（配合 `--persistent-profile`） |
| `--images` | 下载图片到本地 |
| `--videos` | 下载视频（需付费模式 + ffmpeg） |
| `--frontmatter` | `legacy`（默认）或 `mdx` |
| `--chrome-driver-path` | 手动指定 chromedriver 路径 |
| `--edge-driver-path` | 手动指定 msedgedriver 路径 |

## 输出说明

| 目录 | 内容 |
|------|------|
| `substack_md_files/<作者名>/` | 每篇文章的 `.md` 文件 |
| `substack_html_pages/<作者名>/` | 每篇文章的 `.html` 文件和作者主页 |
| `data/<作者名>.json` | 文章元数据（标题、日期、点赞数等） |
| `substack_images/<作者名>/` | 下载的图片（需 `--images`） |
| `substack_videos/<作者名>/` | 下载的视频（需 `--videos`，ffmpeg 转封装为 MP4） |

打开 `substack_html_pages/<作者名>.html` 即可在浏览器中按日期 / 点赞数排序浏览所有文章。

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
├── Screenshot/               # 软件截图
├── assets/
│   ├── css/                  # 样式文件
│   ├── js/                   # 前端 JS（排序 / 切换）
│   └── images/               # 图片资源
├── tests/
│   └── test_substack_scraper.py  # 单元测试
├── data/                     # 文章元数据 JSON（运行时生成）
├── substack_md_files/        # 下载的 Markdown 文件（运行时生成）
├── substack_html_pages/      # 浏览用的 HTML 页面（运行时生成）
├── substack_images/          # 下载的图片（运行时生成）
└── substack_videos/          # 下载的视频（运行时生成）
```

## 运行测试

```bash
pytest tests/ -v
```

## 常见问题

**Q: 提示浏览器驱动错误？**

A: 脚本会自动检测浏览器版本并下载匹配的驱动到 `~/.substack_exporter/drivers/`。如果失败，可以手动下载驱动并用 `--chrome-driver-path` 指定路径。

**Q: 付费模式登录失败 / 出现验证码？**

A: 去掉 `--headless` 参数，加上 `--persistent-profile`，手动完成验证码后，下次用 `--skip-login` 跳过登录。建议直接使用 Web 界面的「登录」按钮，会自动打开可见浏览器窗口。

**Q: 出现 "too many requests"？**

A: 脚本有内置重试机制（指数退避 + 抖动），会自动等待后重试。如果频繁出现，建议减少 `--number` 分批抓取。

**Q: 视频下载后无法播放？**

A: 视频从 HLS 流下载的 TS 分段需要用 ffmpeg 转封装为 MP4。请确保已安装 ffmpeg 并在 PATH 中。抓取时会自动调用 ffmpeg；已下载的旧文件在 Web 界面首次访问时也会自动转换。

## 社区交流

QQ 群：**166710269**

欢迎加入交流 Substack 使用经验、反馈问题和建议。

## 支持作者

开源不易，如果这个项目对你有帮助，欢迎请作者喝杯咖啡 ☕

![微信打赏](https://release.caizhidao.cc/wechatpay.png)

## License

MIT License - 详见 [LICENSE](LICENSE)
