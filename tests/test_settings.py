from pathlib import Path

from app.services.settings import AppSettings, load, save


def test_load_default_when_missing(tmp_path: Path) -> None:
    settings = load(tmp_path / "missing.json")
    assert settings == AppSettings()


def test_load_default_when_corrupt(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{this is not json", encoding="utf-8")
    assert load(target) == AppSettings()


def test_load_default_when_top_level_not_dict(tmp_path: Path) -> None:
    target = tmp_path / "list.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    assert load(target) == AppSettings()


def test_load_ignores_unknown_keys(tmp_path: Path) -> None:
    target = tmp_path / "extra.json"
    target.write_text(
        '{"language": "en", "model": "tiny", "enable_diarization": true, "future_key": 42}',
        encoding="utf-8",
    )
    settings = load(target)
    assert settings.language == "en"
    assert settings.model == "tiny"
    assert settings.enable_diarization is True


def test_save_and_reload_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    original = AppSettings(language="en", model="large-v3", enable_diarization=True)
    save(original, target)
    assert load(target) == original


def test_save_creates_parent_dirs(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dirs" / "config.json"
    save(AppSettings(), target)
    assert target.exists()
