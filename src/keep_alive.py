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


def keep_alive() -> None:
    """Start a lightweight healthcheck server when ENABLE_KEEP_ALIVE=1."""
    if os.getenv("ENABLE_KEEP_ALIVE") != "1":
        return

    host = os.getenv("KEEP_ALIVE_HOST", "0.0.0.0")
    port = int(os.getenv("KEEP_ALIVE_PORT", "8080"))
    thread = threading.Thread(target=_serve, args=(host, port), daemon=True)
    thread.start()
