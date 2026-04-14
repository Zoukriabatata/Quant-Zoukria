param([string]$Url = "")

$envPath = "$PSScriptRoot\.env"
$jtoken  = $null
$dataToken = $null

# ── Methode 1 : URL passee en argument ──────────────────────────────────────
if ($Url -and $Url -like "*jtoken=*") {
    $start  = $Url.IndexOf("jtoken=") + 7
    $end    = $Url.IndexOf("&", $start)
    if ($end -lt 0) { $end = $Url.Length }
    $jtoken = $Url.Substring($start, $end - $start)
    Write-Host "jtoken extrait depuis URL OK"
}

# ── Methode 2 : HAR dans Telechargements ────────────────────────────────────
$harPath = "$env:USERPROFILE\Downloads\4proptrader.com.har"
if (Test-Path $harPath) {
    Write-Host "Lecture HAR..."
    try {
        $har = Get-Content $harPath -Raw | ConvertFrom-Json

        # Cherche jtoken dans les headers referer (si pas deja trouve via URL)
        if (-not $jtoken) {
            foreach ($entry in $har.log.entries) {
                foreach ($h in $entry.request.headers) {
                    if ($h.name -eq "referer" -and $h.value -like "*jtoken=*") {
                        $ref   = $h.value
                        $start = $ref.IndexOf("jtoken=") + 7
                        $end   = $ref.IndexOf("&", $start)
                        if ($end -lt 0) { $end = $ref.Length }
                        $jtoken = $ref.Substring($start, $end - $start)
                        break
                    }
                }
                if ($jtoken) { break }
            }
            if ($jtoken) { Write-Host "jtoken extrait depuis HAR OK" }
        }

        # Cherche le dataToken dxFeed dans les reponses Auth
        foreach ($entry in $har.log.entries) {
            $url = $entry.request.url
            if ($url -like "*/api/connections/dxfeed/Auth*" -or $url -like "*/dxfeed/Auth*") {
                try {
                    $respBody = $entry.response.content.text
                    if ($respBody) {
                        $json = $respBody | ConvertFrom-Json
                        if ($json.success -and $json.data -and $json.data.dataToken) {
                            $dataToken = $json.data.dataToken
                            Write-Host "dataToken dxFeed extrait depuis HAR OK"
                            break
                        }
                    }
                } catch {}
            }
        }
    } catch {
        Write-Host "Erreur lecture HAR: $_"
    }
}

if (-not $jtoken) {
    Write-Host ""
    Write-Host "USAGE : powershell -File update_jtoken.ps1 `"<URL>`""
    Write-Host "1. Ouvre https://4proptrader.com/iframes/volumetric-app/301700"
    Write-Host "2. Copie l URL de la page webapp.volumetricatrading.com"
    Write-Host "3. Colle-la entre guillemets apres le nom du script"
    Write-Host ""
    Write-Host "POUR AUSSI CAPTURER LE DATATOKEN (recommande) :"
    Write-Host "1. Ouvre la page Volumetric dans Chrome"
    Write-Host "2. F12 > Network > filtre 'Auth'"
    Write-Host "3. Attends la requete POST /dxfeed/Auth"
    Write-Host "4. File > Save all as HAR with content"
    Write-Host "5. Depose le HAR dans : $env:USERPROFILE\Downloads\4proptrader.com.har"
    Write-Host "6. Relance ce script"
    Read-Host "Entree pour quitter"
    exit
}

# ── Decode et affiche expiration jtoken ──────────────────────────────────────
$parts = $jtoken.Split(".")
if ($parts.Count -ge 2) {
    $p = $parts[1]
    $pad = $p.Length % 4
    if ($pad) { $p += "=" * (4 - $pad) }
    try {
        $payload = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($p)) | ConvertFrom-Json
        $exp = [DateTimeOffset]::FromUnixTimeSeconds($payload.exp).LocalDateTime
        Write-Host "jtoken valide jusqu au : $exp"
    } catch {
        Write-Host "Impossible de decoder expiration jtoken"
    }
}

# ── Mise a jour .env ─────────────────────────────────────────────────────────
$content = Get-Content $envPath -Raw
$content = $content -replace "VOLUMETRIC_JTOKEN=.*", "VOLUMETRIC_JTOKEN=$jtoken"

if ($dataToken) {
    if ($content -match "DXFEED_DATA_TOKEN=") {
        $content = $content -replace "DXFEED_DATA_TOKEN=.*", "DXFEED_DATA_TOKEN=$dataToken"
    } else {
        $content = $content.TrimEnd() + "`nDXFEED_DATA_TOKEN=$dataToken`n"
    }
    Write-Host "dataToken sauvegarde dans .env — bridge utilisera ce token directement"
} else {
    Write-Host "Pas de dataToken dans le HAR — le bridge passera par Volumetric API ou ATAS"
}

[System.IO.File]::WriteAllText($envPath, $content)

Write-Host ""
Write-Host "OK - .env mis a jour"
Write-Host "Lance : node dxfeed_bridge.js"
Read-Host "Entree pour quitter"
