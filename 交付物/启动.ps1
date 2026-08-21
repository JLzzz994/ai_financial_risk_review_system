[CmdletBinding()]
param(
    [switch]$SeedDemo
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = @(
    "--env-file", (Join-Path $projectRoot ".env"),
    "-f", (Join-Path $projectRoot "docker-compose.yml"),
    "-f", (Join-Path $projectRoot "docker-compose.app.yml")
)

if (-not (Test-Path -LiteralPath (Join-Path $projectRoot ".env"))) {
    throw "缺少项目根目录 .env。请先复制 .env.example 并填写数据库、MinIO、JWT 配置。"
}

Push-Location $projectRoot
try {
    docker compose @compose up -d postgres redis minio milvus-etcd milvus-minio milvus
    docker compose @compose build api worker
    & (Join-Path $PSScriptRoot "数据库初始化.ps1") -Docker:$true -Seed:$SeedDemo
    docker compose @compose up -d api worker

    $front = Join-Path $projectRoot "front"
    if (-not (Test-Path -LiteralPath (Join-Path $front "node_modules"))) {
        npm --prefix $front ci
    }
    npm --prefix $front run dev -- --host 127.0.0.1
}
finally {
    Pop-Location
}
