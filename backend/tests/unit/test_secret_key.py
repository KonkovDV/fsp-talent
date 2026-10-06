"""A fresh `docker compose up` must not run on the published placeholder key, and must not need .env edits."""
import os

from app.core.config import PUBLISHED_SECRETS, Settings, resolve_secret_key


def _settings(tmp_path, key: str = "change-me-use-openssl-rand-hex-32", name: str = "secret_key") -> Settings:
    return Settings(SECRET_KEY=key, SECRET_KEY_FILE=str(tmp_path / name))


def test_placeholder_is_replaced_by_a_generated_key(tmp_path):
    s = _settings(tmp_path)
    resolve_secret_key(s)
    assert s.SECRET_KEY not in PUBLISHED_SECRETS
    assert len(s.SECRET_KEY) == 64
    assert (tmp_path / "secret_key").read_text() == s.SECRET_KEY
    if os.name != "nt":
        assert (tmp_path / "secret_key").stat().st_mode & 0o077 == 0


def test_every_process_reads_the_same_key(tmp_path):
    first, second = _settings(tmp_path), _settings(tmp_path)
    resolve_secret_key(first)
    resolve_secret_key(second)
    assert first.SECRET_KEY == second.SECRET_KEY


def test_explicit_key_is_kept_and_no_file_is_written(tmp_path):
    s = _settings(tmp_path, key="a-private-key-set-by-the-operator")
    resolve_secret_key(s)
    assert s.SECRET_KEY == "a-private-key-set-by-the-operator"
    assert not (tmp_path / "secret_key").exists()


def test_without_a_writable_directory_the_placeholder_stays(tmp_path):
    s = _settings(tmp_path, name="missing-dir/secret_key")
    resolve_secret_key(s)
    assert s.SECRET_KEY in PUBLISHED_SECRETS
