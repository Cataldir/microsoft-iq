"""Local API server for the Foundry IQ demo UI.

Serves the web UI and proxies queries to the Foundry agent.
Run with: python -m foundry-iq.src.api_server
Or:       cd foundry-iq && python src/api_server.py
"""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from query_agent import query_agent


class FoundryIQHandler(SimpleHTTPRequestHandler):
    """Serve the UI and handle /query API calls."""

    def __init__(self, *args, **kwargs):
        # Serve files from the ui/ directory
        ui_dir = str(Path(__file__).resolve().parent.parent / "ui")
        super().__init__(*args, directory=ui_dir, **kwargs)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/query":
            self._handle_query()
        else:
            self.send_error(404)

    def _handle_query(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 10_000:
            self.send_error(413, "Request too large")
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        question = data.get("question", "").strip()
        if not question:
            self.send_error(400, "Missing 'question' field")
            return

        try:
            answer = query_agent(question)
            response = json.dumps({"answer": answer}, ensure_ascii=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response.encode("utf-8"))
        except Exception as exc:
            error_response = json.dumps({"error": str(exc)})
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(error_response.encode("utf-8"))

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """Quieter logging."""
        if "/query" in str(args):
            super().log_message(format, *args)


def main():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("127.0.0.1", port), FoundryIQHandler)
    print(f"Foundry IQ server running at http://localhost:{port}")
    print(f"Open http://localhost:{port} in your browser")
    print("Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
