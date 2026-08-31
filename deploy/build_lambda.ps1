param()
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root '.lambda-build'
$dist = Join-Path $root 'dist'
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $build,$dist | Out-Null
& "$root\.venv\Scripts\python.exe" -m pip install --no-cache-dir --target $build -r "$root\requirements.txt"
Copy-Item "$root\app" $build -Recurse -Force
Copy-Item "$root\lambda_handler.py" $build -Force
Remove-Item "$build\app\__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$dist\amazon-ai-agent-lambda.zip" -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$build\*" -DestinationPath "$dist\amazon-ai-agent-lambda.zip" -Force
Write-Output "Built $dist\amazon-ai-agent-lambda.zip"
