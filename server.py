from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json
import os
import time
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class WeatherHandler(SimpleHTTPRequestHandler):
    cached_forecast = None
    cache_until = 0
    last_modified = None

    @classmethod
    def update_cache_headers(cls, headers, *, not_modified=False):
        # Missing or invalid expiry means revalidate on the next request.
        try:
            cls.cache_until = parsedate_to_datetime(headers.get("Expires", "")).timestamp()
        except (TypeError, ValueError, OverflowError):
            cls.cache_until = 0
        if not_modified:
            cls.last_modified = headers.get("Last-Modified", cls.last_modified)
        else:
            cls.last_modified = headers.get("Last-Modified")

    def do_GET(self):
        if self.path != "/api/forecast":
            return super().do_GET()
        user_agent = os.environ.get("MET_USER_AGENT", "").strip()
        if not user_agent:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Set MET_USER_AGENT with genuine contact information or a project URL"}')
            return
        try:
            if WeatherHandler.cached_forecast is None or time.time() >= WeatherHandler.cache_until:
                headers = {"User-Agent": user_agent}
                if WeatherHandler.cached_forecast is not None and WeatherHandler.last_modified:
                    headers["If-Modified-Since"] = WeatherHandler.last_modified
                request = Request(
                    "https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=60.7945&lon=11.0679",
                    headers=headers,
                )
                try:
                    with urlopen(request, timeout=15) as response:
                        payload = response.read()
                        json.loads(payload)
                        WeatherHandler.cached_forecast = payload
                        WeatherHandler.update_cache_headers(response.headers)
                except HTTPError as error:
                    # urllib represents 304 Not Modified as an HTTPError.
                    try:
                        if error.code != 304 or WeatherHandler.cached_forecast is None:
                            raise
                        WeatherHandler.update_cache_headers(error.headers, not_modified=True)
                    finally:
                        error.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            remaining = max(0, int(WeatherHandler.cache_until - time.time()))
            self.send_header("Cache-Control", f"public, max-age={remaining}")
            self.end_headers()
            self.wfile.write(WeatherHandler.cached_forecast)
        except (URLError, TimeoutError, ValueError, OSError):
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"Forecast temporarily unavailable"}')


if __name__ == "__main__":
    handler = partial(
        WeatherHandler,
        directory=str(Path(__file__).resolve().parent),
    )
    server = HTTPServer(("127.0.0.1", 8000), handler)
    print("http://127.0.0.1:8000")
    server.serve_forever()
