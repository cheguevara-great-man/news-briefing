param(
    [switch]$Discover,
    [string]$InputFile,
    [string[]]$Urls,
    [string]$OutputFile,
    [string]$Sources,
    [string]$Cache,
    [string]$Endpoint = $(if ($env:NEWS_BRIEFING_CDP) { $env:NEWS_BRIEFING_CDP } else { 'http://127.0.0.1:9230' }),
    [ValidateRange(1, 6)]
    [int]$Concurrency = 3,
    [int]$ReadPerSource = 0,
    [switch]$Refresh,
    [string]$ChromePath,
    [string]$ProfilePath,
    [string[]]$ExtensionPaths = @(),
    [string]$ProxyServer,
    [switch]$Headed
)

$ErrorActionPreference = 'Stop'
$newsCollector = Join-Path $PSScriptRoot 'collect_news.py'
try {
    $null = Invoke-RestMethod "$($Endpoint.TrimEnd('/'))/json/version" -TimeoutSec 2
} catch {
    if (-not $ChromePath) {
        throw 'Start Chrome with Start-NewsChrome.ps1 first, or supply -ChromePath to start a dedicated browser.'
    }
    $newsUri = [System.Uri]$Endpoint
    if ($newsUri.Scheme -ne 'http' -or $newsUri.Host -notin @('127.0.0.1', 'localhost')) {
        throw 'Automatic browser startup requires a local HTTP endpoint.'
    }
    $newsLaunchOptions = @{ ChromePath = $ChromePath; Port = $newsUri.Port; ExtensionPaths = $ExtensionPaths }
    if ($ProfilePath) { $newsLaunchOptions.ProfilePath = $ProfilePath }
    if ($ProxyServer) { $newsLaunchOptions.ProxyServer = $ProxyServer }
    if ($Headed) { $newsLaunchOptions.Headed = $true }
    & (Join-Path $PSScriptRoot 'Start-NewsChrome.ps1') @newsLaunchOptions
}

$newsArguments = @('-X', 'utf8', $newsCollector, '--endpoint', $Endpoint, '--concurrency', $Concurrency)
if ($Discover) { $newsArguments += '--discover' }
if ($InputFile) { $newsArguments += @('--input', $InputFile) }
if ($Urls) { $newsArguments += '--urls'; $newsArguments += $Urls }
if ($OutputFile) { $newsArguments += @('--output', $OutputFile) }
if ($Sources) { $newsArguments += @('--sources', $Sources) }
if ($Cache) { $newsArguments += @('--cache', $Cache) }
if ($ReadPerSource) { $newsArguments += @('--read-per-source', $ReadPerSource) }
if ($Refresh) { $newsArguments += '--refresh' }
if (-not $Discover -and -not $InputFile -and -not $Urls) { $newsArguments += '--discover' }

& python @newsArguments
if ($LASTEXITCODE -ne 0) { throw "News collection failed (exit $LASTEXITCODE)." }
