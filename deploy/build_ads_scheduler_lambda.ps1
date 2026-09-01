param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root '.ads-scheduler-lambda-build'
$dist = Join-Path $root 'dist'
$zip = Join-Path $dist 'amazon-ai-agent-ads-scheduler-lambda.zip'
$python = Join-Path $root '.venv_step7\Scripts\python.exe'
$rootFull = [System.IO.Path]::GetFullPath($root).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
$buildFull = [System.IO.Path]::GetFullPath($build)
$zipFull = [System.IO.Path]::GetFullPath($zip)
if (-not $buildFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar) -or (Split-Path $buildFull -Leaf) -ne '.ads-scheduler-lambda-build') { throw 'Unsafe Ads scheduler build path.' }
if (-not $zipFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar) -or (Split-Path $zipFull -Leaf) -ne 'amazon-ai-agent-ads-scheduler-lambda.zip') { throw 'Unsafe Ads scheduler artifact path.' }

# A failed build must never leave an apparently current artifact.
Remove-Item -LiteralPath $build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $build,$dist | Out-Null

try {
    & $python -m pip install `
        --no-cache-dir `
        --platform manylinux2014_x86_64 `
        --implementation cp `
        --python-version 3.14 `
        --only-binary=:all: `
        --target $build `
        -r (Join-Path $PSScriptRoot 'requirements_ads_scheduler_lambda.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Lambda dependency installation failed.' }

    Copy-Item (Join-Path $root 'app') $build -Recurse -Force
    Copy-Item (Join-Path $root 'ads_scheduler_lambda_handler.py') $build -Force
    Remove-Item (Join-Path $build 'bin') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $build 'Scripts') -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $build -Directory -Recurse -Force | Where-Object { $_.Name -eq 'tests' } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $build -Directory -Recurse -Force -Include '__pycache__','.pytest_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $build -File -Recurse -Force -Include '*.db','.env','*.zip' | Remove-Item -Force -ErrorAction SilentlyContinue

    function Test-WindowsPeArtifact([string]$Path) {
        try { $bytes=[System.IO.File]::ReadAllBytes($Path); return $bytes.Length -ge 2 -and $bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A }
        catch { return $false }
    }
    $windowsArtifacts=Get-ChildItem $build -File -Recurse -Force | Where-Object {
        $_.Extension -in '.pyd','.dll','.exe' -or
        ($_.Extension -notin '.py','.pyc' -and $_.Name -match '(?i)(?:^|[._-])(win_amd64|win32)(?:[._-]|$)') -or
        ($_.Name -eq 'WHEEL' -and (Select-String -LiteralPath $_.FullName -Pattern '(?i)\b(win_amd64|win32)\b' -Quiet)) -or
        (Test-WindowsPeArtifact $_.FullName)
    }
    if ($windowsArtifacts) { throw 'Windows-native artifacts found in Ads scheduler Lambda package.' }

    Compress-Archive -Path (Join-Path $build '*') -DestinationPath $zip -Force
    Write-Output "Built $zip for manylinux2014_x86_64 / CPython 3.14"
}
catch {
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    throw
}
finally {
    Remove-Item -LiteralPath $build -Recurse -Force -ErrorAction SilentlyContinue
}
