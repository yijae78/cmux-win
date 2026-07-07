$ErrorActionPreference = 'SilentlyContinue'
$root = Join-Path $env:USERPROFILE '.claude\plugins\cache\superpowers-marketplace\superpowers'
if (-not (Test-Path $root)) { exit 0 }
$bad = "'`${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd'"
$good = '\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\"'
Get-ChildItem -Path $root -Recurse -Filter 'hooks.json' | ForEach-Object {
    $p = $_.FullName
    $c = Get-Content -Path $p -Raw -Encoding UTF8
    if ($c -and $c.Contains($bad)) {
        $c.Replace($bad, $good) | Set-Content -Path $p -Encoding UTF8 -NoNewline
    }
}
exit 0
