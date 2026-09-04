param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root '.web-lambda-build'
$dist = Join-Path $root 'dist'
$zip = Join-Path $dist 'amazon-ai-agent-web-lambda.zip'
$python = Join-Path $root '.venv_step7\Scripts\python.exe'

# A failed build must never leave an apparently current artifact.
Remove-Item -LiteralPath $build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Required project interpreter not found: $python"
}
New-Item -ItemType Directory -Force $build, $dist | Out-Null

try {
    # Cross-package runtime dependencies for AWS Lambda Linux x86_64. --only-binary
    # prevents pip from building or silently using host-specific Windows extensions.
    & $python -m pip install `
        --no-cache-dir `
        --platform manylinux2014_x86_64 `
        --implementation cp `
        --python-version 3.14 `
        --only-binary=:all: `
        --target $build `
        -r (Join-Path $PSScriptRoot 'requirements_web_lambda.txt')
    if ($LASTEXITCODE -ne 0) {
        throw "Lambda dependency installation failed: a compatible Linux x86_64 wheel may be unavailable."
    }

    Copy-Item (Join-Path $root 'app') $build -Recurse -Force
    Copy-Item (Join-Path $root 'templates') $build -Recurse -Force
    Copy-Item (Join-Path $root 'static') $build -Recurse -Force
    Copy-Item (Join-Path $root 'main.py'), (Join-Path $root 'web_lambda_handler.py') $build -Force

    # Remove exact non-runtime directory and file types from dependencies and app content.
    Get-ChildItem $build -Directory -Recurse -Force | Where-Object {
        $_.Name -in 'tests','pytest','_pytest','__pycache__','.pytest_cache','bin','Scripts','.git','.venv','.venv_step7','dist' -or
        $_.Name -like 'pytest*.dist-info'
    } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem $build -File -Recurse -Force | Where-Object {
        $_.Name -eq '.env' -or $_.Extension -in '.db','.sqlite','.sqlite3','.zip'
    } | Remove-Item -Force -ErrorAction SilentlyContinue

    function Test-WindowsPeArtifact([string]$Path) {
        $stream = $null
        try {
            $stream = [System.IO.File]::OpenRead($Path)
            return $stream.ReadByte() -eq 0x4D -and $stream.ReadByte() -eq 0x5A
        } catch {
            return $false
        } finally {
            if ($null -ne $stream) { $stream.Dispose() }
        }
    }

    # Fail rather than package Windows-native extensions, wheel tags, or PE binaries.
    $windowsArtifacts = Get-ChildItem $build -File -Recurse -Force | Where-Object {
        $_.Extension -in '.pyd','.dll','.exe' -or
        ($_.Extension -notin '.py','.pyc' -and $_.Name -match '(?i)(?:^|[._-])(win_amd64|win32)(?:[._-]|$)') -or
        ($_.Name -eq 'WHEEL' -and (Select-String -LiteralPath $_.FullName -Pattern '(?i)\b(win_amd64|win32)\b' -Quiet)) -or
        (Test-WindowsPeArtifact $_.FullName)
    }
    if ($windowsArtifacts) {
        $names = ($windowsArtifacts | Select-Object -ExpandProperty FullName) -join ', '
        throw "Windows-native artifacts found in Lambda package: $names"
    }

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
