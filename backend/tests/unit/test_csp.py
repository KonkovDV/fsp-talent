from pathlib import Path

from app.core.csp import POLICY


def test_the_page_servers_use_the_same_policy():
    root = Path(__file__).resolve().parents[3]
    files = (
        root / "nginx" / "nginx.conf",
        root / "frontend" / "nginx.conf",
        root / "deploy" / "caddy" / "Caddyfile",
    )
    for path in files:
        assert POLICY in path.read_text(encoding="utf-8")
    assert "script-src-attr 'none'" in POLICY
    assert "base-uri 'self'" in POLICY
    assert "'nonce-" not in POLICY
