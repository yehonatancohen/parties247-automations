import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server expects this name
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format, *args):  # noqa: A003 - match base signature
        return


def _serve(host: str, port: int) -> None:
    server = HTTPServer((host, port), _HealthHandler)
    server.serve_forever()


def _is_enabled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def keep_alive() -> None:
    """Start a lightweight healthcheck server when ENABLE_KEEP_ALIVE is truthy."""
    if not _is_enabled(os.getenv("ENABLE_KEEP_ALIVE")):
        return

    host = os.getenv("KEEP_ALIVE_HOST", "0.0.0.0")
    raw_port = os.getenv("KEEP_ALIVE_PORT", "8080")
    try:
        port = int(raw_port)
    except ValueError:
        print(f"⚠️ KEEP_ALIVE_PORT must be an integer (got {raw_port!r}).")
        return
    thread = threading.Thread(target=_serve, args=(host, port), daemon=True)
    thread.start()
