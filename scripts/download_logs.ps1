# PowerShell-скрипт для скачивания логов с сервера

# --- Настройки ---
$serverUser = "root"
$serverHost = "83.222.19.94"
$privateKeyPath = "C:/Users/Lenovo/.ssh/privete-key.ppk"
$remoteLogPath = "/root" # ИСПОЛЬЗУЕМ АБСОЛЮТНЫЙ ПУТЬ ВМЕСТО '~/'
$localLogDirName = "logs"

# --- Логика скрипта ---
Write-Host ">>> Starting log download from $serverHost..."

# Проверка наличия pscp
$pscpPath = Get-Command pscp -ErrorAction SilentlyContinue
if (-not $pscpPath) {
    Write-Host -ForegroundColor Red "Error: pscp.exe not found. Make sure PuTTY tools are installed and in your system's PATH."
    exit 1
}

# Создаем АБСОЛЮТНЫЙ путь к локальной директории для логов
$projectRoot = $PWD.Path
$absoluteLocalLogDir = Join-Path -Path $projectRoot -ChildPath $localLogDirName

# Создаем локальную директорию для логов, если ее нет
if (-not (Test-Path -Path $absoluteLocalLogDir)) {
    New-Item -ItemType Directory -Force -Path $absoluteLocalLogDir | Out-Null
    Write-Host "Created local directory for logs: $absoluteLocalLogDir"
}

# Файлы для скачивания
$logFiles = @("exchanger-worker-logs.txt", "exchanger-creator-logs.txt")

foreach ($file in $logFiles) {
    Write-Host ">>> Downloading $file..."
    $remoteFile = "$($remoteLogPath)/$($file)"
    $localFile = Join-Path -Path $absoluteLocalLogDir -ChildPath $file
    
    # Аргументы для pscp. Указываем директорию назначения, а не полный путь к файлу, для большей надежности.
    $pscpArgs = "-i", $privateKeyPath, "-batch", "$($serverUser)@$($serverHost):$remoteFile", "./logs"
    
    # Прямой вызов pscp для корректной обработки кодов выхода
    & pscp.exe @pscpArgs

    if ($LASTEXITCODE -eq 0) {
        # Сообщение об успехе использует $localFile, так как это полный путь к скачанному файлу.
        Write-Host -ForegroundColor Green "✅ Successfully downloaded to $localFile"
    }
    else {
        Write-Host -ForegroundColor Red "❌ Failed to download $file. Please check the error message from pscp above."
    }
}

Write-Host ">>> Log download process finished."
Read-Host "Press Enter to exit..." 