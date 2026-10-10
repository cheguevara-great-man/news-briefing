# News Briefing

把“打开几十家新闻网站找内容”变成“先扫标题，挑值得读的，再按编号追问”。

这个工具通过本机 Chrome 批量扫描新闻入口、提取文章正文，保存结构化 JSON。你可以让 AI 助手基于这些内容整理当天的中文简报，再按编号展开讨论。浏览器沿用自己的登录状态和扩展，日常采集使用后台标签。

它负责采集，不负责自动评判新闻价值、核验全文或生成 AI 摘要；后面这些交给你或 AI 助手。无需配置任何模型 API Key。

## 能做什么

- 内置40个媒体入口，覆盖财经、国际关系、科技和科学。包含收费媒体与公开媒体；Politico的美国和欧洲入口属于同一品牌。
- 扫描标题和链接，再读取指定文章，避免把主页推荐顺序当成新闻价值排序。
- 连接现有 Chrome，通过 CDP 创建后台标签，只关闭本次创建的标签。
- 默认同时处理3页，同一媒体一次处理1页。
- 清理追踪参数、按URL去重和缓存。读取缓存时不重新开文章。
- 分别记录可读、收费提示、验证拦截、提取不完整和错误。

## 安装

需要 Python 3.10+、一个支持 CDP 的 Chrome/Chromium 浏览器。Windows提供启动脚本，Python采集器也可连接Linux、macOS上已经启动的浏览器。

```powershell
git clone https://github.com/cheguevara-great-man/news-briefing.git
cd news-briefing
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Linux/macOS激活环境用 `source .venv/bin/activate`。采集器连接外部浏览器，不需要运行 `playwright install`。

## 启动浏览器

### Windows

推荐使用独立的 [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/)，解压后把实际的 `chrome.exe` 路径传给脚本：

```powershell
.\Start-NewsChrome.ps1 -ChromePath 'C:\tools\chrome-win64\chrome.exe'
```

默认使用独立的 `%LOCALAPPDATA%\NewsBriefing\ChromeProfile`，CDP端口为9230。浏览器默认以无窗口模式启动，不弹出窗口。已有该端口时直接复用，不改变现有浏览器的运行模式。

可选参数：

```powershell
.\Start-NewsChrome.ps1 `
  -ChromePath 'C:\tools\chrome-win64\chrome.exe' `
  -ProfilePath 'C:\news-profile' `
  -Port 9230 `
  -ExtensionPaths @('C:\extensions\my-extension')
```

`-ExtensionPaths`接收解压后含`manifest.json`的目录；是否允许命令行加载扩展取决于浏览器版本和发行渠道。普通Chrome可能限制此参数。第三方扩展、安装来源及许可证由使用者自行选择，本仓库不附带扩展。

需要登录订阅或配置扩展时，先按浏览器和扩展说明在这个独立profile中完成一次配置，关闭它，再用后台脚本启动。某些扩展还要求开启开发者模式或允许用户脚本，不能仅凭参数出现就认定扩展已正常工作。

`-ProxyServer 'http://127.0.0.1:8080'`可配置代理。无窗口模式下的扩展兼容性需要实际检查；需要正常浏览器环境时可加`-Headed`，脚本会隐藏窗口并将其移到屏幕外，但启动时仍可能短暂抢焦点。多个独立浏览器使用不同profile和端口。

### 已有浏览器 / Linux / macOS

让浏览器使用独立profile并开启本机CDP，例如Linux：

```bash
chromium --headless=new \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9230 \
  --user-data-dir="$HOME/.local/share/news-briefing/chrome"
```

macOS使用Chrome应用里的可执行文件，参数相同。使用扩展时，应按所用浏览器的支持情况选择正常或无窗口模式。

CDP可以控制浏览器及其登录会话，应保持在本机回环地址。采集器直接连接CDP，无需另装Browser Gateway服务或扩展。

## 日常用法

### 1. 先扫标题

```powershell
python collect_news.py --discover --output reports/discovery.json
```

打开结果的`candidates`列表，按时效、信息增量和兴趣挑选文章。默认每个入口最多12个候选，`--limit`可调整。标题和链接不代表已读取正文。

### 2. 读取选中的文章

把选单保存为`reports/selected.json`。支持URL数组，或包含`url`、可选`source`和`title`的对象数组：

```json
[
  {
    "source": "Example News",
    "title": "替换为实际候选标题",
    "url": "https://example.com/article/replace-this"
  }
]
```

```powershell
python collect_news.py --input reports/selected.json --output reports/articles.json
```

读取单篇也一样：

```powershell
python collect_news.py --urls 'https://example.com/article/replace-this'
```

选单也可以直接使用发现报告，但这会读取其中全部候选。URL示例是占位符，不是可读新闻样本。

### 3. 核验后生成简报

让AI助手读取本地结果，确认正文完整性和发表日期，再按[简报模板](examples/brief-template.md)生成`briefs/YYYY-MM-DD.md`。可给助手这样的任务：

> 扫描配置的新闻来源，对照已有简报去重，再选择值得读的候选并获取正文。逐篇确认是否完整，区分事实、评论、匿名说法和未落实计划。生成今天日期命名的中文文档，包含编号、速览、简短梗概、日期和原文链接。我之后按编号追问。分别汇报候选数、试读数、完整正文数和收录数，并记录未收录原因。

项目里的[AGENTS.md](AGENTS.md)提供这一工作流程。助手需要具备本地文件和命令执行能力；JSON也可以自行阅读或交给其他工具处理。模型调用、编辑筛选、跨日去重和文档生成并未内置于采集器。

### PowerShell快捷入口

```powershell
.\Collect-News.ps1 -Discover -OutputFile reports/discovery.json
.\Collect-News.ps1 -InputFile reports/selected.json -OutputFile reports/articles.json
```

可以传`-ChromePath`让它在本机端口不可用时启动浏览器；其余启动选项与`Start-NewsChrome.ps1`一致。

需要快速初读时：

```powershell
.\Collect-News.ps1 -Discover -ReadPerSource 3
```

这只是读取每个入口网页顺序靠前的3个候选，没有新闻价值评分。平时推荐先扫描，再人工或由助手精选。

## 参数和输出

| 参数 | 默认值 / 用途 |
| --- | --- |
| `--endpoint` | `http://127.0.0.1:9230`，也可用`NEWS_BRIEFING_CDP`环境变量 |
| `--sources` | 项目中的`sources.json` |
| `--cache` | Windows：`%LOCALAPPDATA%\NewsBriefing`；其他系统：`$XDG_CACHE_HOME/news-briefing`或`~/.cache/news-briefing` |
| `--output` | 缓存目录内的`discovery-latest.json`或`articles-latest.json` |
| `--concurrency` | 3，允许1—6；同一媒体仍限制为1 |
| `--timeout` | 每页18秒 |
| `--limit` | 每个入口12个候选 |
| `--days` | 7，仅过滤URL中可识别为`YYYY/MM/DD`的旧链接 |
| `--refresh` | 跳过缓存 |
| `--read-per-source` | 扫描后初读每个入口指定数量的候选 |

缓存目录也可用`NEWS_BRIEFING_CACHE`指定。完整参数见`python collect_news.py --help`。

报告包含`collected_at`、耗时和`results`。文章结果包含URL、来源、标题、发表元数据、状态、原因，以及取得的`text`和`paragraphs`。`text`中也可能包含推荐、作者介绍等，需要确认正文边界；短简讯可能被保守地标成`incomplete`。

| 状态 | 含义 |
| --- | --- |
| `discovered` | 发现候选链接，尚未读文章 |
| `readable` | 找到足量正文段落，**不保证完整全文** |
| `paywall` | 仍有订阅提示 |
| `blocked` | 验证页或访问拦截 |
| `incomplete` | 没找到正文，或只取得短导语 |
| `error` | 超时等执行错误 |

可读正文缓存24小时，扫描和失败结果缓存15分钟。缓存文件名是清理后URL的SHA256，**不是正文哈希**。不同URL报道同一事件、跨日重复和转载，需要另外对照历史简报；本项目没有长期“已收录索引”。日期过滤也不是所有站点通用，主页上的旧推荐仍要检查。

## 扩展媒体和运行检查

在`sources.json`增加`name`、`url`、`domain`和`article_pattern`即可新增扫描入口。文章结构变化时，检查`collect_news.py`中的`EXTRACT`选择器和订阅、验证判定规则。

```powershell
python -m unittest discover -s . -p 'test_*.py' -v
```

现有测试覆盖订阅导语、推荐段落误判、安全验证、追踪参数去重、域名边界、日期优先级、缓存路径和CLI参数。

[GitHub Actions配置示例](examples/github-actions-tests.yml)覆盖Windows、Linux和Python 3.10、3.14。要启用自动测试，可在自己的仓库中把它保存为`.github/workflows/tests.yml`；当前仓库未启用该工作流。

## 开源范围

MIT许可证适用于本项目代码。新闻文章和第三方扩展的版权、访问权限保持其原有规定。公开仓库包含代码、媒体入口、测试和模板；正文缓存、登录profile、代理配置和个人日报保存在使用者本机。
