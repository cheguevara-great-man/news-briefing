param(
    [Parameter(Mandatory = $true)]
    [string]$ChromePath,
    [string]$ProfilePath = (Join-Path $env:LOCALAPPDATA 'NewsBriefing/ChromeProfile'),
    [ValidateRange(1, 65535)]
    [int]$Port = 9230,
    [string[]]$ExtensionPaths = @(),
    [string]$ProxyServer,
    [switch]$Headed
)

$ErrorActionPreference = 'Stop'
$newsEndpoint = "http://127.0.0.1:$Port/json/version"
try {
    $newsStatus = Invoke-RestMethod $newsEndpoint -TimeoutSec 2
} catch {
    $newsStatus = $null
}
if ($newsStatus) {
    Write-Output "Browser already available on port $Port ($($newsStatus.Browser))."
    return
}

$newsChrome = (Resolve-Path -LiteralPath $ChromePath).Path
$newsProfile = [System.IO.Path]::GetFullPath($ProfilePath)
New-Item -ItemType Directory -Path $newsProfile -Force | Out-Null
$newsExtensions = @($ExtensionPaths | ForEach-Object {
    $newsExtension = (Resolve-Path -LiteralPath $_).Path
    if (-not (Test-Path -LiteralPath (Join-Path $newsExtension 'manifest.json'))) {
        throw "Extension directory has no manifest.json: $newsExtension"
    }
    $newsExtension
})

# Start-Process joins arguments into a command line; quote paths with spaces.
$newsArguments = @(
    '--remote-debugging-address=127.0.0.1'
    "--remote-debugging-port=$Port"
    "--user-data-dir=`"$newsProfile`""
    '--no-first-run'
    '--no-default-browser-check'
    '--window-position=-32000,-32000'
    '--window-size=1200,800'
)
if ($newsExtensions.Count) {
    $newsArguments += "--load-extension=`"$($newsExtensions -join ',')`""
}
if ($ProxyServer) { $newsArguments += "--proxy-server=`"$ProxyServer`"" }
if (-not $Headed) { $newsArguments += '--headless=new' }
$newsArguments += 'about:blank'

# Preserve extension-compatible headed Chrome while keeping it offscreen.
if ($Headed -and -not ('NewsBriefingWindow' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class NewsBriefingWindow {
    private delegate bool WindowCallback(IntPtr window, IntPtr state);
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(WindowCallback callback, IntPtr state);
    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint processId);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr window, StringBuilder name, int capacity);
    [DllImport("user32.dll")]
    private static extern bool SetWindowPos(IntPtr window, IntPtr after, int x, int y,
        int width, int height, uint flags);

    public static void MoveOffscreen(int processId) {
        EnumWindows((window, state) => {
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            if (owner != processId) return true;
            var name = new StringBuilder(128);
            GetClassName(window, name, name.Capacity);
            if (name.ToString().StartsWith("Chrome_WidgetWin", StringComparison.Ordinal))
                SetWindowPos(window, IntPtr.Zero, -32000, -32000, 1200, 800, 0x0014);
            return true;
        }, IntPtr.Zero);
    }
}
'@
}

$newsBrowser = Start-Process -FilePath $newsChrome -ArgumentList $newsArguments -WindowStyle Hidden -PassThru
for ($newsAttempt = 0; $newsAttempt -lt 60; $newsAttempt++) {
    if ($Headed) { [NewsBriefingWindow]::MoveOffscreen($newsBrowser.Id) }
    try {
        $newsStatus = Invoke-RestMethod $newsEndpoint -TimeoutSec 1
    } catch {
        $newsStatus = $null
    }
    if ($newsStatus) {
        Write-Output "News browser ready on port $Port ($($newsStatus.Browser)); process $($newsBrowser.Id)."
        return
    }
    if ($newsBrowser.HasExited) { throw 'Chrome exited before its CDP endpoint became available.' }
    Start-Sleep -Milliseconds 250
}
throw "Browser did not become available at $newsEndpoint. Check the browser path, profile and port."
