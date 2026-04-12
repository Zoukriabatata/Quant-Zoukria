# Cherche le token JWT DXFeed le plus récent dans les logs ATAS
# Essaie dxapi.log (actif) puis dxapi.log.0 (rotaté) — prend le plus récent

$base = $env:APPDATA + "\ATAS\Connectors\dxFeed prop\"
$files = @("dxapi.log", "dxapi.log.0", "dxapi.log.1")

$allTokens = @()

foreach ($f in $files) {
    $path = $base + $f
    if (-not (Test-Path $path)) { continue }
    try {
        $stream = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
        $reader = New-Object System.IO.StreamReader($stream)
        $content = $reader.ReadToEnd()
        $reader.Close(); $stream.Close()
        $matches2 = [regex]::Matches($content, 'token:\s*(\S+)')
        foreach ($m in $matches2) {
            $allTokens += $m.Groups[1].Value
        }
    } catch {}
}

if ($allTokens.Count -gt 0) {
    # Retourne le dernier token trouvé (le plus récent chronologiquement)
    Write-Output $allTokens[$allTokens.Count - 1]
}
