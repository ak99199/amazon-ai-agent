param()

$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root '.web-lambda-build'
$dist = Join-Path $root 'dist'
$python = Join-Path $root '.venv\Scripts\python.exe'

Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $build, $dist | Out-Null

# Cross-package runtime dependencies for AWS Lambda Linux x86_64. --only-binary
# prevents pip from building or silently using host-specific Windows extensions.
& $python -m pip install `
    --no-cache-dir `
    --platform manylinux2014_x86_64 `
    --implementation cp `
    --python-version 3.14 `
    --only-binary=:all: `
    --target $build `
    -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    throw "Lambda dependency installation failed: a compatible Linux x86_64 wheel may be unavailable."
}

Copy-Item (Join-Path $root 'app') $build -Recurse -Force
Copy-Item (Join-Path $root 'templates') $build -Recurse -Force
Copy-Item (Join-Path $root 'static') $build -Recurse -Force
Copy-Item (Join-Path $root 'main.py'), (Join-Path $root 'web_lambda_handler.py') $build -Force
Get-ChildItem $build -Directory -Recurse -Force -Include '__pycache__', '.pytest_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Fail rather than package obvious Windows-native files or Windows wheel metadata.
$windowsArtifacts = Get-ChildItem $build -File -Recurse -Force | Where-Object {
    $_.Name -match '(?i)win_amd64|\.pyd$' -or
    ($_.Name -eq 'WHEEL' -and (Select-String -LiteralPath $_.FullName -Pattern '(?i)win_amd64|win32' -Quiet))
}
if ($windowsArtifacts) {
    $names = ($windowsArtifacts | Select-Object -ExpandProperty FullName) -join ', '
    throw "Windows-native artifacts found in Lambda package: $names"
}

Remove-Item (Join-Path $dist 'amazon-ai-agent-web-lambda.zip') -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $build '*') -DestinationPath (Join-Path $dist 'amazon-ai-agent-web-lambda.zip') -Force
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
Write-Output "Built $(Join-Path $dist 'amazon-ai-agent-web-lambda.zip') for manylinux2014_x86_64 / CPython 3.14"
