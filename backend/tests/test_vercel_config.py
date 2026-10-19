import json
import tomllib
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_vercel_installs_from_requirements_txt() -> None:
    config = json.loads((BACKEND_DIR / "vercel.json").read_text(encoding="utf-8"))
    install_command = config.get("installCommand", "")
    assert "requirements.txt" in install_command
    assert install_command.startswith("uv pip install")


def test_pyproject_has_no_project_table() -> None:
    # A [project] table would make Vercel's builder treat pyproject.toml as the
    # dependency manifest and ignore requirements.txt. Keep it config-only.
    data = tomllib.loads((BACKEND_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    assert "project" not in data


def test_no_uv_lock_hijacks_manifest_detection() -> None:
    # A uv.lock next to pyproject.toml is the highest-priority manifest for
    # Vercel's builder, which would bypass installCommand's requirements.txt.
    assert not (BACKEND_DIR / "uv.lock").exists()
