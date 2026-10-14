# News Briefing

把“打开几十家新闻网站找内容”变成“先扫标题，挑值得读的，再按编号追问”。

这个工具通过本机 Chrome 批量扫描新闻入口、提取文章正文，保存结构化 JSON。你可以让 AI 助手基于这些内容整理当天的中文简报，再按编号展开讨论。浏览器沿用自己的登录状态和扩展，日常采集使用后台标签。

它负责采集，不负责自动评判新闻价值、核验全文或生成 AI 摘要；后面这些交给你或 AI 助手。无需配置任何模型 API Key。

**付费媒体正文依赖浏览器中的访问能力。** 原始工作流使用 **Bypass Paywalls Clean** 扩展；采集器本身不解锁付费墙。只安装Python依赖，可以扫公开标题、读取公开文章，但不能复现原始工作流的付费媒体阅读效果。下面包含扩展下载、首次配置、后台加载及检查步骤。

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

## 安装和配置付费墙扩展

使用 [Bypass Paywalls Clean for Chrome](https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean)。本项目提供安装脚本，从该扩展上游README列出的地址下载ZIP，保留其原始许可证，解压到本机永久目录。它是独立的第三方项目，归属与许可证见[第三方依赖说明](THIRD_PARTY.md)。

```powershell
.\Install-NewsExtension.ps1
```

默认安装到`%LOCALAPPDATA%\NewsBriefing\Extensions\bypass-paywalls-chrome-clean`，启动脚本会自动加载这里的扩展。安装脚本显示实际版本和下载包SHA256；哈希用于记录这次下载，不是上游签名。再次运行会复用已安装版本，不覆盖扩展文件。原始工作流使用v4.4.2.6，在线安装取得上游当时提供的版本。

下载受网络限制时，先从[上游下载页面](https://gitflic.ru/project/magnolia1234/bpc_uploads)保存ZIP，再运行：

```powershell
.\Install-NewsExtension.ps1 -ArchivePath 'C:\Downloads\bypass-paywalls-chrome-clean-master.zip'
```

首次配置需要一个可见窗口，在同一个独立浏览器profile里完成：

```powershell
.\Start-NewsChrome.ps1 -ChromePath 'C:\tools\chrome-win64\chrome.exe' -Setup
```

1. 在打开的`chrome://extensions/`页面开启“开发者模式”，确认Bypass Paywalls Clean存在且已启用。若浏览器没有接受命令行加载，点击“加载已解压的扩展程序”，选择上述永久目录。
2. 检查扩展详情中的网站访问权限，以及扩展选项里的目标站点开关。某些版本或其他扩展若要求“允许用户脚本”，按其说明启用；这个选项并非所有版本都需要。
3. 打开一篇目标媒体的付费文章，确认实际正文能够显示。扩展出现在列表里不代表每个站点都可读。
4. 完全退出这个独立新闻浏览器，再按下节启动后台模式。profile中的扩展设置会保留，日常采集无需再次弹出配置窗口。

`-Setup`专门用于首次配置，会显示窗口；日常命令不加它。若该CDP端口已有浏览器，配置模式会提示先退出或改用另一组profile和端口，不会悄悄把后台浏览器切换为可见窗口。

更新扩展按[上游更新说明](https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean)操作，保留安装目录，随后重启独立新闻浏览器。也可用`-Destination`安装到新的空目录，并在启动时传入对应的`-ExtensionPaths`；不要删除浏览器正在使用的目录。

## 启动浏览器

### Windows

推荐使用独立的 [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/)，解压后把实际的 `chrome.exe` 路径传给脚本：

```powershell
.\Start-NewsChrome.ps1 -ChromePath 'C:\tools\chrome-win64\chrome.exe'
```

默认使用独立的 `%LOCALAPPDATA%\NewsBriefing\ChromeProfile`，CDP端口为9230。浏览器默认以无窗口模式启动，不弹出窗口。已有该端口时直接复用，不改变现有浏览器的运行模式。

未显式传入`-ExtensionPaths`时，脚本自动使用上一节的默认扩展目录；默认目录没有扩展时会提示。已经运行的浏览器只会被复用，不会因新的命令参数重新安装或加载扩展。

可选参数：

```powershell
.\Start-NewsChrome.ps1 `
  -ChromePath 'C:\tools\chrome-win64\chrome.exe' `
  -ProfilePath 'C:\news-profile' `
  -Port 9230 `
  -ExtensionPaths @('C:\extensions\my-extension')
```

`-ExtensionPaths`接收解压后含`manifest.json`的目录，可用于已有的Bypass Paywalls Clean或其他扩展；是否允许命令行加载取决于浏览器版本和发行渠道，普通Chrome可能限制此参数。指定这个参数会替代默认扩展列表，需要多个扩展时一起传入。

需要登录订阅或配置扩展时，先按浏览器和扩展说明在这个独立profile中完成一次配置，关闭它，再用后台脚本启动。某些扩展还要求开启开发者模式或允许用户脚本，不能仅凭参数出现就认定扩展已正常工作。

`-ProxyServer 'http://127.0.0.1:8080'`可配置代理。无窗口模式下的扩展兼容性需要实际检查；需要正常浏览器环境时可加`-Headed`，脚本会隐藏窗口并将其移到屏幕外，但启动时仍可能短暂抢焦点。多个独立浏览器使用不同profile和端口。

浏览器也需要能实际访问目标媒体。Python能下载扩展，不代表Chrome已经使用相同的网络代理；若本机设置了可供Chrome使用的`HTTPS_PROXY`，可显式传入`-ProxyServer $env:HTTPS_PROXY`，首次配置和日常启动保持一致。代理地址只保存在本机，不要写进公开仓库。

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

### 检查扩展是否加载

```powershell
python check_news_browser.py
# 非默认端口：
python check_news_browser.py --endpoint http://127.0.0.1:9231
```

检查命令使用一个后台标签，输出浏览器版本、Bypass Paywalls Clean版本、启用状态、开发者模式和用户脚本权限信息，仅关闭自己创建的标签。未找到扩展、扩展被禁用或连接失败时返回非零退出码。开发者模式未开启不一定意味着已安装扩展无法运行，用户脚本权限也不是所有版本都必需。

`ok: true`只确认扩展启用。最后仍需用`python collect_news.py --urls '实际文章URL' --refresh`试读，检查正文和结尾。仍出现`paywall`时，检查目标站点开关、权限和版本；`blocked`还可能是验证码或访问限制。扩展支持列表与本项目40个扫描入口是两回事，不能承诺所有文章都能取得全文。

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

可以传`-ChromePath`让它在本机端口不可用时启动浏览器，也可传`-ProfilePath`、`-ExtensionPaths`、`-ProxyServer`和`-Headed`。首次可见配置请单独运行`Start-NewsChrome.ps1 -Setup`。

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

**《经济学人》文章回退**：采集器先在原站尝试读取正文；若带日期的 `economist.com` 文章被标记为 `paywall`、`incomplete` 或 `blocked`，依次试读 `freedium-mirror.cfd` 和 `wallhop.io`。只有镜像返回足量段落且标题与原文吻合，才把原文章状态改为 `readable`，同时写入 `original_status` 和 `retrieved_via`。`source` 和原始 URL 保持为《经济学人》。这两个镜像不是永久保证可用的全文来源，`readable` 仍需人工确认文章结尾；`archive.today` 当前不在自动回退列表中。

| 状态 | 含义 |
| --- | --- |
| `discovered` | 发现候选链接，尚未读文章 |
| `readable` | 找到足量正文段落，**不保证完整全文** |
| `paywall` | 仍有订阅提示 |
| `blocked` | 验证页或访问拦截 |
| `incomplete` | 没找到正文，或只取得短导语 |
| `error` | 超时等执行错误，或浏览器网络错误页 |

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
