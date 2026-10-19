import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[3] / "deploy" / "verify_backup.py"
spec = importlib.util.spec_from_file_location("verify_backup", MODULE)
verify_backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_backup)


def test_a_custom_dump_with_the_tables_passes(tmp_path):
    payload = b"PGDMP" + b"\x00" * 120
    for name in (b"participants", b"employers", b"offers", b"test_sessions", b"consents"):
        payload += name + b"\x00"
    path = tmp_path / "ok.dump"
    path.write_bytes(payload)
    assert verify_backup.verify_dump(path) == []


def test_a_text_file_and_a_dump_missing_a_table_fail(tmp_path):
    text = tmp_path / "nope.txt"
    text.write_bytes(b"hello database")
    errors = verify_backup.verify_dump(text)
    assert any("не дамп" in line for line in errors)
    assert any("маленьк" in line for line in errors)
    partial = tmp_path / "partial.dump"
    partial.write_bytes(b"PGDMP" + b"\x00" * 120 + b"participants\x00employers\x00")
    missed = verify_backup.verify_dump(partial)
    assert any("offers" in line for line in missed)
    assert not any("не дамп" in line for line in missed)


def test_a_restore_set_needs_the_signing_key(tmp_path):
    empty = tmp_path / "keys"
    empty.mkdir()
    assert any("ключа" in line for line in verify_backup.verify_key_dir(empty))
    pem = empty / "vc_ed25519.pem"
    pem.write_bytes(b"not-a-real-key-but-long-enough-for-the-check")
    assert verify_backup.verify_key_dir(empty) == []
