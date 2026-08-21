[CmdletBinding()]
param(
    [switch]$Docker,
    [switch]$Seed
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($Docker) {
    $compose = @(
        "--env-file", (Join-Path $projectRoot ".env"),
        "-f", (Join-Path $projectRoot "docker-compose.yml"),
        "-f", (Join-Path $projectRoot "docker-compose.app.yml")
    )
    docker compose @compose run --rm --no-deps api uv run alembic upgrade head
    if ($Seed) {
        docker compose @compose run --rm --no-deps api uv run python seed_demo_data.py
    }
    exit 0
}

Push-Location $projectRoot
try {
    uv run alembic upgrade head
    if ($Seed) { uv run python seed_demo_data.py }
}
finally {
    Pop-Location
}
