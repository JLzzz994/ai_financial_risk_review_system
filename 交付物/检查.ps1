$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$compose = @(
    "--env-file", (Join-Path $projectRoot ".env"),
    "-f", (Join-Path $projectRoot "docker-compose.yml"),
    "-f", (Join-Path $projectRoot "docker-compose.app.yml")
)

Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health/live | Select-Object -ExpandProperty Content
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health/ready | Select-Object -ExpandProperty Content
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/ | Select-Object -ExpandProperty StatusCode
docker compose @compose ps
