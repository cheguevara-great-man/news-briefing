# 第三方依赖

## Bypass Paywalls Clean for Chrome

- 作者：magnolia1234。
- 上游项目：https://gitflic.ru/project/magnolia1234/bypass-paywalls-chrome-clean
- 上游下载：https://gitflic.ru/project/magnolia1234/bpc_uploads
- 许可证：MIT；上游版权声明为`Copyright (c) 2020, magnolia1234`，以取得版本附带的许可证为准。
- 原始新闻工作流使用版本：4.4.2.6。

`Install-NewsExtension.ps1`从上游文档提供的ZIP地址下载扩展，在使用者本机安装，保留扩展文件及许可证。本仓库不把第三方扩展改名为自己的代码，也不复制个人浏览器profile、扩展设置或cookies。在线下载的版本可能变化，安装时会显示实际版本和下载包哈希。

采集器通过CDP读取浏览器当前实际显示的内容；扩展在浏览器中执行各站点规则。扫描入口、内容提取和缓存由本项目负责，付费墙处理由扩展负责。扩展规则可能涉及页面脚本、请求、cookies或其他内容来源，具体行为以所安装版本的源码和上游说明为准。

MIT许可不转移新闻文章版权。扩展是否支持一个站点，不保证该站点的所有文章都能访问或取得完整正文。

## Playwright 与 Chrome

采集器依赖Python的Playwright包连接CDP。Chrome/Chromium浏览器由使用者单独安装；Windows建议使用Chrome for Testing，以便运行独立profile和加载解压扩展。

Browser Gateway用于其他浏览器操作方式，本项目的直接CDP采集无需安装它。
