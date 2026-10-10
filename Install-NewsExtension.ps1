param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'NewsBriefing/Extensions/bypass-paywalls-chrome-clean'),
    [string]$ArchivePath
)

$ErrorActionPreference = 'Stop'
$newsDestination = [System.IO.Path]::GetFullPath($Destination)
$newsManifestPath = Join-Path $newsDestination 'manifest.json'
if (Test-Path -LiteralPath $newsDestination) {
    if (-not (Test-Path -LiteralPath $newsManifestPath)) {
        throw 'Destination already exists without manifest.json. Choose an empty destination.'
    }
    $newsManifest = Get-Content -LiteralPath $newsManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($newsManifest.name -ne 'Bypass Paywalls Clean') {
        throw 'Destination contains a different extension. Choose an empty destination.'
    }
    Write-Output "Reusing Bypass Paywalls Clean $($newsManifest.version): $newsDestination"
    return
}

$newsTempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$newsTemp = Join-Path $newsTempRoot ('news-briefing-extension-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $newsTemp | Out-Null
try {
    $newsArchive = Join-Path $newsTemp 'bpc.zip'
    if ($ArchivePath) {
        Copy-Item -LiteralPath (Resolve-Path -LiteralPath $ArchivePath).Path -Destination $newsArchive
    } else {
        # Official download from the extension's own README; never use a third-party mirror.
        $newsUrl = 'https://gitflic.ru/project/magnolia1234/bpc_uploads/blob/raw?file=bypass-paywalls-chrome-clean-master.zip'
        Invoke-WebRequest -Uri $newsUrl -OutFile $newsArchive -UseBasicParsing -TimeoutSec 60
    }
    $newsHash = (Get-FileHash -LiteralPath $newsArchive -Algorithm SHA256).Hash
    $newsUnpacked = Join-Path $newsTemp 'unpacked'
    Expand-Archive -LiteralPath $newsArchive -DestinationPath $newsUnpacked
    $newsRoots = @($newsUnpacked) + @(Get-ChildItem -LiteralPath $newsUnpacked -Directory | ForEach-Object { $_.FullName })
    $newsMatches = @($newsRoots | Where-Object {
        $newsCandidate = Join-Path $_ 'manifest.json'
        if (Test-Path -LiteralPath $newsCandidate) {
            $newsInfo = Get-Content -LiteralPath $newsCandidate -Raw -Encoding UTF8 | ConvertFrom-Json
            $newsInfo.name -eq 'Bypass Paywalls Clean'
        }
    })
    if ($newsMatches.Count -ne 1) { throw 'Archive must contain one Bypass Paywalls Clean extension root.' }
    $newsSource = [System.IO.Path]::GetFullPath($newsMatches[0])
    $newsLicense = Join-Path $newsSource 'LICENSE.txt'
    if (-not (Test-Path -LiteralPath $newsLicense)) { $newsLicense = Join-Path $newsSource 'LICENSE' }
    if (-not (Test-Path -LiteralPath $newsLicense)) { throw 'Extension archive is missing its license.' }
    $newsManifest = Get-Content -LiteralPath (Join-Path $newsSource 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $newsManifest.version -or -not (Test-Path -LiteralPath (Join-Path $newsSource $newsManifest.background.service_worker))) {
        throw 'Extension archive is missing its version or background service worker.'
    }
    if (-not $newsSource.StartsWith($newsTemp + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Extension source is outside the temporary extraction directory.'
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $newsDestination) -Force | Out-Null
    # Source is checked above; destination is the explicit installation directory.
    Move-Item -LiteralPath $newsSource -Destination $newsDestination
    Write-Output "Installed Bypass Paywalls Clean $($newsManifest.version): $newsDestination"
    Write-Output "Downloaded archive SHA256: $newsHash (record only, not an upstream signature)."
    Write-Output 'Next: run Start-NewsChrome.ps1 -ChromePath <chrome.exe> -Setup for first-time browser configuration.'
} finally {
    $newsResolvedTemp = [System.IO.Path]::GetFullPath($newsTemp)
    $newsTempPrefix = $newsTempRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    if ($newsResolvedTemp.StartsWith($newsTempPrefix, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $newsResolvedTemp).StartsWith('news-briefing-extension-')) {
        Remove-Item -LiteralPath $newsResolvedTemp -Recurse -Force
    }
}
