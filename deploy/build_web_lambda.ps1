param()
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root '.web-lambda-build'
$dist = Join-Path $root 'dist'
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $build,$dist | Out-Null
& "$root\.venv\Scripts\python.exe" -m pip install --no-cache-dir --target $build -r "$root\requirements.txt"
Copy-Item "$root\app" $build -Recurse -Force
Copy-Item "$root\templates" $build -Recurse -Force
Copy-Item "$root\static" $build -Recurse -Force
Copy-Item "$root\main.py","$root\web_lambda_handler.py" $build -Force
Get-ChildItem $build -Directory -Recurse -Force -Include '__pycache__','.pytest_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$dist\amazon-ai-agent-web-lambda.zip" -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$build\*" -DestinationPath "$dist\amazon-ai-agent-web-lambda.zip" -Force
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
Write-Output "Built $dist\amazon-ai-agent-web-lambda.zip"
