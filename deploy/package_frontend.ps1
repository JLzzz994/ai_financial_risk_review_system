[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist",
    [string]$Version = (Get-Date -Format "yyyyMMdd-HHmmss")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendDist = Join-Path $repoRoot "front/dist"
$outputRoot = Join-Path $repoRoot $OutputDirectory
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("financial-review-frontend-" + [guid]::NewGuid().ToString("N"))
$archivePath = Join-Path $outputRoot ("financial-review-frontend-{0}.zip" -f $Version)

try {
    if (-not (Test-Path -LiteralPath $frontendDist -PathType Container)) {
        throw "未找到前端构建目录，请先执行: cd front; npm run build"
    }

    $packageRoot = Join-Path $stagingRoot "frontend-dist"
    New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null
    Get-ChildItem -LiteralPath $frontendDist -Force | Copy-Item -Destination $packageRoot -Recurse -Force

    New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    Compress-Archive -Path $packageRoot -DestinationPath $archivePath -CompressionLevel Optimal

    $archiveSizeMb = [math]::Round((Get-Item -LiteralPath $archivePath).Length / 1MB, 2)
    Write-Output ("已生成前端部署包: {0} ({1} MB)" -f $archivePath, $archiveSizeMb)
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
