# update_jtoken.ps1 — Extrait le jtoken depuis un HAR et met a jour .env
# Usage: double-clic ou powershell -File update_jtoken.ps1

$harPath = "$env:USERPROFILE\Downloads\4proptrader.com.har"
$envPath = "$PSScriptRoot\.env"

if (-not (Test-Path $harPath)) {
    Write-Host "HAR introuvable: $harPath"
    Write-Host "-> Ouvre la page volumetric dans Chrome, F12 > Network > Exporter HAR"
    Read-Host "Appuie sur Entree pour quitter"
    exit
}

$har = Get-Content $harPath -Raw | ConvertFrom-Json
$jtoken = $null

foreach ($entry in $har.log.entries) {
    foreach ($h in $entry.request.headers) {
        if ($h.name -eq "referer" -and $h.value -like "*jtoken=*") {
            $ref = $h.value
            $start = $ref.IndexOf("jtoken=") + 7
            $end = $ref.IndexOf("&", $start)
            if ($end -lt 0) { $end = $ref.Length }
            $jtoken = $ref.Substring($start, $end - $start)
            break
        }
    }
    if ($jtoken) { break }
}

if (-not $jtoken) {
    Write-Host "jtoken non trouve dans le HAR"
    Read-Host "Appuie sur Entree pour quitter"
    exit
}

$parts = $jtoken.Split(".")
if ($parts.Count -ge 2) {
    $p = $parts[1]; $pad = $p.Length % 4
    if ($pad) { $p += "=" * (4 - $pad) }
    try {
        $payload = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | ConvertFrom-Json
        $exp = [DateTimeOffset]::FromUnixTimeSeconds($payload.exp).LocalDateTime
        Write-Host "jtoken valide jusqu'au: $exp"
    } catch {}
}

$content = Get-Content $envPath -Raw
$content = $content -replace "VOLUMETRIC_JTOKEN=.*", "VOLUMETRIC_JTOKEN=$jtoken"
[System.IO.File]::WriteAllText($envPath, $content)

Write-Host "OK .env mis a jour avec le nouveau jtoken"
Write-Host "Lance: node dxfeed_bridge.js"
Read-Host "Appuie sur Entree pour quitter"
