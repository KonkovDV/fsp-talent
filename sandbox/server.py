"""HTTP over a Unix socket for the API container. Standard library only.

POST /run {"language", "source", "cases"} -> {"outputs", "timed_out"}
GET /health -> {"ok": true, "languages": [...]}
`python server.py --health` is the container health check.
"""
from __future__ import annotations

import hmac
import json
import os
import socket
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler

from runner import available_languages, run

SOCKET = os.environ.get("SANDBOX_SOCKET", "/run/sandbox/sandbox.sock")
TOKEN = os.environ.get("SANDBOX_TOKEN", "")
SLOTS = threading.BoundedSemaphore(int(os.environ.get("SANDBOX_CONCURRENCY", "2")))
MAX_BODY = 64 * 1024
MAX_SOURCE = 16 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "fsp-sandbox"

    def log_message(self, *args) -> None:   # a Unix peer has no address; the API logs the request
        return

    def address_string(self) -> str:
        return "unix"

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            return self._send(200, {"ok": True, "languages": available_languages()})
        return self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/run":
            return self._send(404, {"error": "not_found"})
        if TOKEN and not hmac.compare_digest(self.headers.get("X-Sandbox-Token", ""), TOKEN):
            return self._send(403, {"error": "forbidden"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {"error": "too_large"})
        try:
            req = json.loads(self.rfile.read(length).decode("utf-8"))
            language, source, cases = req["language"], req["source"], req["cases"]
            if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_SOURCE:
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return self._send(400, {"error": "bad_request"})
        if not SLOTS.acquire(timeout=10):
            return self._send(503, {"error": "busy"})
        try:
            result = run(language, source, cases)
        finally:
            SLOTS.release()
        return self._send(400 if "error" in result else 200, result)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def health() -> int:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(3)
            sock.connect(SOCKET)
            sock.sendall(b"GET /health HTTP/1.0\r\n\r\n")
            return 0 if b" 200 " in sock.recv(256) else 1
    except OSError:
        return 1


def main() -> None:
    if os.path.exists(SOCKET):
        os.unlink(SOCKET)
    with Server(SOCKET, Handler) as server:
        os.chmod(SOCKET, 0o666)   # the API runs under another uid in its own container
        server.serve_forever()


if __name__ == "__main__":
    sys.exit(health()) if "--health" in sys.argv else main()
