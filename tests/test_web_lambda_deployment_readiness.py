from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "deploy" / "build_web_lambda.ps1"
RUNTIME_REQUIREMENTS = ROOT / "deploy" / "requirements_web_lambda.txt"


def runtime_requirements():
    return {
        line.strip().lower()
        for line in RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_web_build_uses_verified_environment_and_prunes_non_runtime_content():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert ".venv_step7\\Scripts\\python.exe" in script
    assert "'.venv\\Scripts\\python.exe'" not in script
    assert "Join-Path $PSScriptRoot 'requirements_web_lambda.txt'" in script
    assert "Join-Path $root 'requirements.txt'" not in script
    for excluded in ("tests", ".venv", ".venv_step7", ".env", ".db", ".git", "dist"):
        assert excluded in script
    for test_dependency in ("'pytest'", "'_pytest'", "'pytest*.dist-info'"):
        assert test_dependency in script


def test_runtime_manifest_has_production_dependencies_without_pytest():
    requirements = runtime_requirements()
    assert "pytest" not in requirements
    assert requirements == {
        "fastapi",
        "requests",
        "python-dotenv",
        "boto3",
        "openai",
        "httpx",
        "jinja2",
        "bcrypt",
        "python-multipart",
        "itsdangerous",
        "mangum",
    }


def test_native_guards_reject_binaries_but_allow_pure_python_win32_names():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    for native_guard in (".pyd", ".dll", ".exe", "win_amd64", "win32", "WHEEL", "Test-WindowsPeArtifact"):
        assert native_guard in script
    assert "$_.Extension -notin '.py','.pyc'" in script
    assert "ReadAllBytes" not in script
    assert "$stream.ReadByte() -eq 0x4D" in script


def test_recursive_app_package_contains_control_plane_runtime_modules():
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "Copy-Item (Join-Path $root 'app') $build -Recurse -Force" in script
    for module in (
        "ads_control_plane_base.py",
        "ads_control_plane_factory.py",
        "ads_control_plane_dynamodb_repository.py",
    ):
        assert (ROOT / "app" / "database" / module).is_file()


def test_documented_historical_and_control_plane_environment_contracts_are_separate():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    historical = (
        "AMAZON_ADS_STORAGE_BACKEND=dynamodb",
        "AMAZON_ADS_DYNAMODB_PERFORMANCE_TABLE=<configured table name>",
        "AMAZON_ADS_DYNAMODB_SYNC_RUNS_TABLE=<configured table name>",
    )
    control_plane = (
        "AMAZON_ADS_CONTROL_PLANE_BACKEND=dynamodb",
        "AMAZON_ADS_DYNAMODB_CONTROL_PLANE_TABLE=<configured table name>",
    )
    assert all(value in readme for value in historical)
    assert all(value in readme for value in control_plane)
    assert len(set(historical + control_plane)) == 5
