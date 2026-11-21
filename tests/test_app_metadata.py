from pathlib import Path

from app.main import app


def test_api_version_matches_release_version() -> None:
    version_path = Path(__file__).resolve().parents[1] / "version.txt"

    assert app.version == version_path.read_text(encoding="utf-8").strip()
