$ErrorActionPreference = 'Stop'

$archiveUrl = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.1-essentials_build.zip'
$expectedVersion = 'ffmpeg-9.0.1-essentials_build'
$expectedChecksum = 'fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9'
$projectRoot = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $projectRoot 'assets\ffmpeg'
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('neiva-ffmpeg-' + [guid]::NewGuid().ToString('N'))
$archive = Join-Path $temporaryRoot 'ffmpeg.zip'

try {
    New-Item -ItemType Directory -Path $temporaryRoot | Out-Null
    & curl.exe --fail --location --retry 3 --retry-delay 5 --connect-timeout 30 --max-time 600 --silent --show-error --output $archive $archiveUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível baixar o FFmpeg (curl: $LASTEXITCODE)."
    }

    $actualChecksum = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualChecksum -ne $expectedChecksum) {
        throw "O SHA-256 do FFmpeg não corresponde à versão aprovada: $actualChecksum"
    }

    Expand-Archive -LiteralPath $archive -DestinationPath $temporaryRoot
    $source = Join-Path $temporaryRoot $expectedVersion
    if (-not (Test-Path -LiteralPath $source -PathType Container)) {
        throw "A pasta esperada não existe no pacote: $expectedVersion"
    }

    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source 'bin\ffmpeg.exe') -Destination $destination -Force
    Copy-Item -LiteralPath (Join-Path $source 'bin\ffprobe.exe') -Destination $destination -Force
    Copy-Item -LiteralPath (Join-Path $source 'LICENSE') -Destination (Join-Path $destination 'LICENSE.GPLv3.txt') -Force
    Copy-Item -LiteralPath (Join-Path $source 'README.txt') -Destination (Join-Path $destination 'BUILD_INFO.txt') -Force
    Write-Host "FFmpeg $expectedVersion preparado em $destination"
}
finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force
    }
}
