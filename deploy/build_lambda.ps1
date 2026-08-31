param()

$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root '.lambda-build'
$dist = Join-Path $root 'dist'
$zip = Join-Path $dist 'amazon-ai-agent-lambda.zip'
$python = Join-Path $root '.venv\Scripts\python.exe'

# Remove any prior artifact before work begins, so a failed build cannot appear current.
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
Remove-Item $zip -Force -ErrorAction SilentlyContinue
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
Copy-Item (Join-Path $root 'lambda_handler.py') $build -Force

# pip may generate host-specific console launchers on Windows. They are not used by Lambda.
Remove-Item (Join-Path $build 'bin') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $build 'Scripts') -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $build -Directory -Recurse -Force -Include '__pycache__', '.pytest_cache' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

function Test-WindowsPeArtifact([string]$Path) {
    try {
        $bytes = [System.IO.File]::ReadAllBytes($Path)
        return $bytes.Length -ge 2 -and $bytes[0] -eq 0x4D -and $bytes[1] -eq 0x5A
    } catch {
        return $false
    }
}

# Reject Windows-native extensions, explicit native Windows tags, and PE binaries.
# Python source filenames such as colorama/win32.py are intentionally permitted.
$windowsArtifacts = Get-ChildItem $build -File -Recurse -Force | Where-Object {
    $nativeExtension = $_.Extension -in '.pyd', '.dll', '.exe'
    $taggedBinaryName = $_.Extension -notin '.py', '.pyc' -and $_.Name -match '(?i)(?:^|[._-])(win_amd64|win32)(?:[._-]|$)'
    $taggedWheelMetadata = $_.Name -eq 'WHEEL' -and (Select-String -LiteralPath $_.FullName -Pattern '(?i)\b(win_amd64|win32)\b' -Quiet)
    $nativeExtension -or $taggedBinaryName -or $taggedWheelMetadata -or (Test-WindowsPeArtifact $_.FullName)
}
if ($windowsArtifacts) {
    $names = ($windowsArtifacts | Select-Object -ExpandProperty FullName) -join ', '
    throw "Windows-native artifacts found in Lambda package: $names"
}

Compress-Archive -Path (Join-Path $build '*') -DestinationPath $zip -Force
Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue
Write-Output "Built $zip for manylinux2014_x86_64 / CPython 3.14"