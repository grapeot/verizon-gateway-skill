"""Build only a synthetic staged tree; never copy local runtime artifacts."""

from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile


MODULES = {"__init__.py", "auth.py", "cli.py", "client.py", "config.py",
           "monitor.py", "storage.py", "telemetry.py", "py.typed"}
SENTINEL = "example-" + "private-sentinel"


def check_wheel(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        package = {name.removeprefix("verizon_gateway/") for name in names
                   if name.startswith("verizon_gateway/")}
        assert package == MODULES
        assert all(name.startswith("verizon_gateway/") or ".dist-info/" in name for name in names)
        assert all(SENTINEL.encode() not in archive.read(name) for name in names)


def test_distribution_excludes_runtime_and_unexpected_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    stage = tmp_path / "stage"
    stage.mkdir()
    public = ["pyproject.toml", "README.md", "AGENTS.md", "LICENSE", ".env.example", ".gitignore"]
    public += [f"src/verizon_gateway/{name}" for name in MODULES]
    public += [f"docs/{name}" for name in ("prd.md", "rfc.md", "test.md", "working.md")]
    public += ["skills/verizon-gateway/SKILL.md", ".github/workflows/ci.yml"]
    public += [str(path.relative_to(root)) for path in (root / "tests").glob("*.py")]
    for name in public:
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    for name in (".env", ".local/credentials.json", "data/telemetry.sqlite",
                 "logs/output.log", "src/verizon_gateway/unexpected.txt",
                 "src/verizon_gateway/.local/credentials.json"):
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(SENTINEL)
    result = subprocess.run([sys.executable, "-m", "build", "--no-isolation"],
                            cwd=stage, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    check_wheel(next((stage / "dist").glob("*.whl")))
    with tarfile.open(next((stage / "dist").glob("*.tar.gz"))) as archive:
        names = [member.name.split("/", 1)[1] for member in archive.getmembers() if member.isfile()]
        assert set(names) == set(public) | {"PKG-INFO"}
        assert all(SENTINEL.encode() not in archive.extractfile(member).read()
                   for member in archive.getmembers() if member.isfile())
        extracted = tmp_path / "extracted"
        archive.extractall(extracted, filter="data")
    rebuilt = next(extracted.iterdir())
    result = subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--wheel"],
                            cwd=rebuilt, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    check_wheel(next((rebuilt / "dist").glob("*.whl")))
