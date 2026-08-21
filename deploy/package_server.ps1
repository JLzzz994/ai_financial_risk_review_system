[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist",
    [string]$Version = (Get-Date -Format "yyyyMMdd-HHmmss")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRoot = Join-Path $repoRoot $OutputDirectory
$stagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("financial-review-package-" + [guid]::NewGuid().ToString("N"))
$packageRoot = Join-Path $stagingRoot "financial-review"
$archivePath = Join-Path $outputRoot ("financial-review-server-{0}.zip" -f $Version)

$includedPaths = @(
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.app.yml",
    "docker-compose.server.yml",
    "docker-compose.server-existing-infra.yml",
    ".env.example",
    "requirements.txt",
    "pyproject.toml",
    "uv.lock",
    "alembic.ini",
    "seed_demo_data.py",
    "deploy/run_service.sh",
    "deploy/package_frontend.ps1",
    "deploy/systemd/financial-review-api.service",
    "deploy/systemd/financial-review-worker.service",
    "deploy/服务器部署说明.md",
    "docs/使用说明.md"
)
$includedDirectories = @("app", "engines", "alembic", "front")
$excludedDirectoryNames = @(
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    "var", "logs", "uploads"
)

try {
    New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

    foreach ($relativePath in $includedPaths) {
        $sourcePath = Join-Path $repoRoot $relativePath
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            Write-Warning "跳过不存在的文件: $relativePath"
            continue
        }
        $targetPath = Join-Path $packageRoot $relativePath
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetPath) | Out-Null
        Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
    }

    foreach ($relativeDirectory in $includedDirectories) {
        $sourceDirectory = Join-Path $repoRoot $relativeDirectory
        if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
            Write-Warning "跳过不存在的目录: $relativeDirectory"
            continue
        }
        Get-ChildItem -LiteralPath $sourceDirectory -Recurse -File | Where-Object {
            $relativeFile = [System.IO.Path]::GetRelativePath($repoRoot, $_.FullName)
            $parts = $relativeFile -split [regex]::Escape([System.IO.Path]::DirectorySeparatorChar)
            -not ($parts | Where-Object { $excludedDirectoryNames -contains $_ })
        } | ForEach-Object {
            $relativeFile = [System.IO.Path]::GetRelativePath($repoRoot, $_.FullName)
            $targetPath = Join-Path $packageRoot $relativeFile
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetPath) | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $targetPath -Force
        }
    }

    # Dockerfile 会 COPY var；打包时保留空目录，但不带入真实上传文件和日志。
    foreach ($relativeDirectory in @("var", "var/uploads", "var/logs")) {
        New-Item -ItemType Directory -Force -Path (Join-Path $packageRoot $relativeDirectory) | Out-Null
    }

    New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
    if (Test-Path -LiteralPath $archivePath) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    Compress-Archive -Path $packageRoot -DestinationPath $archivePath -CompressionLevel Optimal

    $archiveSizeMb = [math]::Round((Get-Item -LiteralPath $archivePath).Length / 1MB, 2)
    Write-Output ("已生成部署包: {0} ({1} MB)" -f $archivePath, $archiveSizeMb)
    Write-Output "包内不包含 .venv、node_modules、Python/site-packages、上传文件和日志。"
}
finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}
