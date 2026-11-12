"""Serve the offline Hamar Access Lab planning workspace on 127.0.0.1.

Start with: python hamar_workspace.py
"""

import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE / "harness"))
from workspace_service import BusyError, Workspace

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY = 32 * 1024
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
POSTS = {"/api/fingerprint": "fingerprint", "/api/assess": "assess", "/api/compare": "compare",
         "/api/journey": "resolve_journey", "/api/bus/assess": "assess_bus"}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class WorkspaceServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port=DEFAULT_PORT, opener=urlopen, root=HERE):
        self.workspace = Workspace(root, opener)
        self.root = Path(root)
        super().__init__((HOST, port), Handler)

    @property
    def allowed_hosts(self):
        port = self.server_address[1]
        return {f"{HOST}:{port}", f"localhost:{port}"}


class Handler(BaseHTTPRequestHandler):
    server_version = "HamarWorkspace"

    def log_message(self, format, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def _send(self, status, body, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload, ensure_ascii=True).encode("ascii"))

    def _local_request(self, post):
        if self.headers.get("Host") not in self.server.allowed_hosts:
            self._json(403, {"error": "Requests must use the local address"})
            return False
        origin = self.headers.get("Origin")
        local_origins = {f"http://{host}" for host in self.server.allowed_hosts}
        if post and origin is not None and origin not in local_origins:
            self._json(403, {"error": "Cross-origin requests are not allowed"})
            return False
        return True

    def do_GET(self):
        if not self._local_request(False):
            return
        path = self.path.split("?", 1)[0]
        if path in STATIC:
            name, content_type = STATIC[path]
            try:
                body = (self.server.root / "workspace" / name).read_bytes()
            except OSError:
                self._json(404, {"error": "Not found"})
                return
            self._send(200, body, content_type)
        elif path == "/api/cases":
            self._json(200, self.server.workspace.index())
        elif path == "/api/bus":
            self._json(200, self.server.workspace.bus_scenario())
        elif path == "/api/bus/published":
            self._json(200, self.server.workspace.published_bus_scenario())
        elif path.startswith("/api/cases/") and "/" not in path[len("/api/cases/"):]:
            try:
                self._json(200, self.server.workspace.case_payload(path[len("/api/cases/"):]))
            except LookupError:
                self._json(404, {"error": "Unknown case"})
        else:
            self._json(404, {"error": "Not found"})

    do_HEAD = do_GET

    def do_POST(self):
        if not self._local_request(True):
            return
        path = self.path.split("?", 1)[0]
        method = POSTS.get(path)
        if method is None:
            self._json(404, {"error": "Not found"})
            return
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            self._json(415, {"error": "Send application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json(411, {"error": "Content-Length is required"})
            return
        if not 0 < length <= MAX_BODY:
            self._json(413, {"error": f"Request body must be 1 to {MAX_BODY} bytes"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._json(400, {"error": "Request body is not valid JSON"})
            return
        try:
            self._json(200, getattr(self.server.workspace, method)(payload))
        except BusyError as exc:
            self._json(409, {"error": str(exc)})
        except LookupError as exc:
            self._json(404, {"error": str(exc)})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            sys.stderr.write("Unexpected workspace error\n")
            self._json(500, {"error": "Unexpected error; see the server console"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--open", action="store_true", help="Open the workspace in the default browser")
    args = parser.parse_args()
    try:
        server = WorkspaceServer(args.port)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Workspace could not start: {exc}\n")
    url = f"http://{HOST}:{server.server_address[1]}/"
    print(f"Hamar Access Lab workspace: {url}")
    print("Offline except explicit local Ollama requests. Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
