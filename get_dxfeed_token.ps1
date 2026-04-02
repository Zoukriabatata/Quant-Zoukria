$logPath = $env:APPDATA + "\ATAS\Connectors\dxFeed prop\dxapi.log.0"
$stream = [System.IO.File]::Open($logPath, 'Open', 'Read', 'ReadWrite')
$reader = New-Object System.IO.StreamReader($stream)
$content = $reader.ReadToEnd()
$reader.Close(); $stream.Close()
$matches2 = [regex]::Matches($content, 'token:\s*(\S+)')
if ($matches2.Count -gt 0) {
    # Dernier token = session la plus récente
    Write-Output $matches2[$matches2.Count - 1].Groups[1].Value
}
