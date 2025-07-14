# PowerShell-скрипт для скачивания логов с сервера

# --- Настройки ---
$serverUser = "root"
$serverHost = "83.222.19.94"
$privateKeyPath = "C:/Users/Lenovo/.ssh/privete-key.ppk"
$remoteLogPath = "~/"
$localLogDir = "logs"

# --- Логика скрипта ---
Write-Host ">>> Starting log download from $serverHost..."

# Проверка наличия pscp
$pscpPath = Get-Command pscp -ErrorAction SilentlyContinue
if (-not $pscpPath) {
    Write-Host -ForegroundColor Red "Error: pscp.exe not found. Make sure PuTTY tools are installed and in your system's PATH."
    exit 1
}

# Создаем локальную директорию для логов, если ее нет
if (-not (Test-Path -Path $localLogDir)) {
    New-Item -ItemType Directory -Force -Path $localLogDir | Out-Null
    Write-Host "Created local directory for logs: $localLogDir"
}

# Файлы для скачивания
$logFiles = @("exchanger-worker-logs.txt", "exchanger-creator-logs.txt")

foreach ($file in $logFiles) {
    Write-Host ">>> Downloading $file..."
    $remoteFile = "$remoteLogPath/$file"
    $localFile = Join-Path -Path $localLogDir -ChildPath $file
    
    $pscpArgs = "-i", $privateKeyPath, "-batch", "$($serverUser)@$($serverHost):$remoteFile", $localFile
    
    try {
        Start-Process -FilePath "pscp.exe" -ArgumentList $pscpArgs -Wait -NoNewWindow
        Write-Host -ForegroundColor Green "✅ Successfully downloaded to $localFile"
    }
    catch {
        Write-Host -ForegroundColor Red "❌ Failed to download $file. Error: $_"
    }
}

Write-Host ">>> Log download process finished."
Read-Host "Press Enter to exit..." 