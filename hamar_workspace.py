"""Serve the offline Hamar Access Lab planning workspace on 127.0.0.1.

Start with: python hamar_workspace.py
"""

import argparse
import json
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE / "harness"))
from workspace_service import BusyError, Workspace
from harness.city_notices import notice_feed
from harness.official_notices import OfficialNotices

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY = 32 * 1024
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/notifications.js": ("notifications.js", "text/javascript; charset=utf-8"),
    "/bus-catalogue.js": ("bus-catalogue.js", "text/javascript; charset=utf-8"),
    "/preferences.js": ("preferences.js", "text/javascript; charset=utf-8"),
    "/geographic-map.js": ("geographic-map.js", "text/javascript; charset=utf-8"),
    "/vendor/maplibre/maplibre-gl.mjs": ("vendor/maplibre/maplibre-gl.mjs", "text/javascript; charset=utf-8"),
    "/vendor/maplibre/maplibre-gl-worker.mjs": ("vendor/maplibre/maplibre-gl-worker.mjs", "text/javascript; charset=utf-8"),
    "/vendor/maplibre/maplibre-gl-shared.mjs": ("vendor/maplibre/maplibre-gl-shared.mjs", "text/javascript; charset=utf-8"),
    "/vendor/maplibre/maplibre-gl.css": ("vendor/maplibre/maplibre-gl.css", "text/css; charset=utf-8"),
}
POSTS = {"/api/fingerprint": "fingerprint", "/api/assess": "assess", "/api/compare": "compare",
         "/api/journey": "resolve_journey", "/api/bus/assess": "assess_bus",
         "/api/notice/draft": "draft_koigen_notice",
         "/api/monitor-scenario": "monitor_scenario",
         "/api/journey-alerts": "journey_alerts"}
OFFICIAL_POSTS = {"/api/official-notices/check": "check", "/api/official-notices/accept": "accept"}
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; worker-src 'self'; style-src 'self'; "
        "img-src 'self' data: blob: https://tiles.openfreemap.org; "
        "connect-src 'self' https://tiles.openfreemap.org; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
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
        self.official_notices = OfficialNotices(self.root)
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
        elif path == "/api/notifications":
            try:
                notices = notice_feed(self.server.root)
            except (OSError, ValueError, KeyError, TypeError, IndexError):
                self._json(503, {"error": "Saved Hamar notices are unavailable."})
            else:
                self._json(200, {"notices": notices})
        elif path == "/api/official-notices":
            try:
                self._json(200, self.server.official_notices.review_queue())
            except (OSError, ValueError):
                self._json(503, {"error": "Saved source reviews are unavailable."})
        elif path == "/api/bus/catalogue" or path.startswith("/api/bus/catalogue/"):
            try:
                from harness.bus_catalogue import query
                tail = path[len("/api/bus/catalogue/"):] if path.startswith("/api/bus/catalogue/") else None
                if tail is not None and (not tail or "/" in urllib.parse.unquote(tail)):
                    raise LookupError("Unknown imported bus line")
                args = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                self._json(200, query(self.server.root, urllib.parse.unquote(tail) if tail else None, args.get("pattern", [None])[0]))
            except LookupError as exc:
                self._json(404, {"error": str(exc)})
            except (OSError, ValueError, KeyError) as exc:
                self._json(503, {"error": "Imported bus data unavailable; use the saved comparison examples."})
        elif path == "/api/bus":
            self._json(200, self.server.workspace.bus_scenario())
        elif path == "/api/bus/published":
            self._json(200, self.server.workspace.published_bus_scenario())
        elif path.startswith("/api/bus/published/") and "/" not in path[len("/api/bus/published/"):]:
            try:
                self._json(200, self.server.workspace.published_bus_scenario(path[len("/api/bus/published/"):]))
            except LookupError:
                self._json(404, {"error": "Unknown published bus case"})
        elif path.startswith("/api/cases/") and "/" not in path[len("/api/cases/"):]:
            try:
                self._json(200, self.server.workspace.case_payload(path[len("/api/cases/"):]))
            except LookupError:
                self._json(404, {"error": "Unknown case"})
        elif path == "/api/places":
            query = urllib.parse.parse_qs(self.path.split("?", 1)[1]).get("q", [""])[0] \
                if "?" in self.path else ""
            try:
                self._json(200, self.server.workspace.search_places(query))
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
        elif path == "/api/project-records":
            query = urllib.parse.parse_qs(self.path.split("?", 1)[1]).get("revision", ["current"])[0] \
                if "?" in self.path else "current"
            try:
                self._json(200, self.server.workspace.project_records(query))
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
        else:
            self._json(404, {"error": "Not found"})

    do_HEAD = do_GET

    def do_POST(self):
        if not self._local_request(True):
            return
        path = self.path.split("?", 1)[0]
        official_method = OFFICIAL_POSTS.get(path)
        method = official_method or POSTS.get(path)
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
            service = self.server.official_notices if official_method else self.server.workspace
            self._json(200, getattr(service, method)(payload))
        except (BusyError, BlockingIOError) as exc:
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
    print("Official notice checks and Ollama requests are initiated from the workspace. Press Ctrl+C to stop.")
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
