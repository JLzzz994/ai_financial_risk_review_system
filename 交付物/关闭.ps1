$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = @(
    "--env-file", (Join-Path $projectRoot ".env"),
    "-f", (Join-Path $projectRoot "docker-compose.yml"),
    "-f", (Join-Path $projectRoot "docker-compose.app.yml")
)

if (Test-Path -LiteralPath (Join-Path $projectRoot ".env")) {
    docker compose @compose stop api worker postgres redis minio milvus milvus-etcd milvus-minio
}
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*$([IO.Path]::DirectorySeparatorChar)front$([IO.Path]::DirectorySeparatorChar)*"
} | Stop-Process -Force -ErrorAction SilentlyContinue
