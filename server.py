#!/usr/bin/env python3
"""
Super Investing · Research Agent Web Server
Minimalist White & Black UI Dashboard
"""

import os
import sys
import json
import socket
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from agent import (
    load_env_file,
    load_research_pack,
    build_agent_payload,
    generate_research_brief,
    execute_research_pipeline_stream,
)

load_env_file()

WEB_DIR = os.path.join(BASE_DIR, "web")


class ResearchAgentHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for local development
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. API: Server Status
        if path == "/api/status":
            has_key = bool(os.getenv("OPENAI_API_KEY"))
            self.send_json({"status": "ok", "has_api_key": has_key})
            return

        # 2. API: Document List & Cache Check
        if path == "/api/docs":
            docs_dir = query.get("docs_dir", ["./research_pack"])[0]
            if not os.path.isabs(docs_dir):
                docs_dir = os.path.normpath(os.path.join(BASE_DIR, docs_dir))

            existing_brief = ""
            brief_file = os.path.join(BASE_DIR, "brief_srvcable.md")
            if os.path.exists(brief_file):
                with open(brief_file, "r", encoding="utf-8") as f:
                    existing_brief = f.read()

            try:
                docs, profile, conflicts = load_research_pack(docs_dir, "SRVCABLE")
                doc_summaries = [
                    {
                        "filename": d["filename"],
                        "source": d["source"],
                        "published": d["published"],
                        "credibility": d["credibility"],
                        "flags": d["flags"],
                    }
                    for d in docs
                ]
                self.send_json({
                    "docs": doc_summaries,
                    "profile": profile,
                    "existing_brief": existing_brief
                })
            except Exception as e:
                self.send_json({"error": str(e), "docs": []}, status=500)
            return

        if path in ["/api/run-stream", "/api/run_stream"]:
            flat_params = {k: v[0] for k, v in query.items() if v}
            self.handle_stream_request(flat_params)
            return

        # 3. Static File Serving (web/)
        if path in ["/", "/index.html"]:
            self.serve_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
        elif path == "/style.css":
            self.serve_file(os.path.join(WEB_DIR, "style.css"), "text/css; charset=utf-8")
        elif path == "/app.js":
            self.serve_file(os.path.join(WEB_DIR, "app.js"), "application/javascript; charset=utf-8")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/run":
            length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(length)
            try:
                data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                data = {}

            ticker = data.get("ticker", "SRVCABLE").strip().upper()
            model = data.get("model", "gpt-4o-mini").strip()
            docs_dir = data.get("docs_dir", "./research_pack").strip()
            api_key = data.get("api_key", "").strip() or os.getenv("OPENAI_API_KEY")

            if not os.path.isabs(docs_dir):
                docs_dir = os.path.normpath(os.path.join(BASE_DIR, docs_dir))

            try:
                # Stage 1: Load and inspect
                docs, target_profile, conflicts = load_research_pack(docs_dir, ticker)

                alerts = []
                for d in docs:
                    for f in d["flags"]:
                        alerts.append({"file": d["filename"], "flag": f})

                # Build dossier
                dossier = build_agent_payload(docs, target_profile, conflicts)

                # Stage 2: Synthesis
                prompt_file = os.path.join(BASE_DIR, "system_prompt.md")
                with open(prompt_file, "r", encoding="utf-8") as f:
                    system_prompt = f.read()

                brief = generate_research_brief(dossier, system_prompt, model=model, api_key=api_key)

                # Save brief to file as well
                output_path = os.path.join(BASE_DIR, f"brief_{ticker.lower()}.md")
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(brief)

                doc_summaries = [
                    {
                        "filename": d["filename"],
                        "source": d["source"],
                        "published": d["published"],
                        "credibility": d["credibility"],
                        "flags": d["flags"],
                    }
                    for d in docs
                ]

                self.send_json({
                    "brief": brief,
                    "alerts": alerts,
                    "conflicts": conflicts,
                    "dossier": dossier,
                    "docs": doc_summaries,
                    "profile": target_profile,
                })

            except Exception as e:
                self.send_json({"error": str(e)}, status=500)
            return

        if parsed.path in ["/api/run-stream", "/api/run_stream"]:
            length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except Exception:
                data = {}
            self.handle_stream_request(data)
            return

        self.send_error(404, "Not Found")

    def handle_stream_request(self, params: dict):
        ticker = params.get("ticker", "SRVCABLE").strip().upper()
        model = params.get("model", "gpt-4o-mini").strip()
        docs_dir = params.get("docs_dir", "./research_pack").strip()
        api_key = params.get("api_key", "").strip() or os.getenv("OPENAI_API_KEY")

        if not os.path.isabs(docs_dir):
            docs_dir = os.path.normpath(os.path.join(BASE_DIR, docs_dir))

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        prompt_file = os.path.join(BASE_DIR, "system_prompt.md")
        try:
            for event_name, payload in execute_research_pipeline_stream(
                docs_dir=docs_dir,
                ticker=ticker,
                model=model,
                api_key=api_key,
                system_prompt_file=prompt_file
            ):
                msg = f"event: {event_name}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
                self.wfile.write(msg)
                self.wfile.flush()
        except Exception as e:
            err_msg = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n".encode("utf-8")
            try:
                self.wfile.write(err_msg)
                self.wfile.flush()
            except Exception:
                pass
        finally:
            self.close_connection = True

    def serve_file(self, filepath: str, content_type: str):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Clean terminal logging
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")


def find_available_port(preferred_ports=[8080, 5050, 5000, 8888]):
    for port in preferred_ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 8080


def run_server(port: int = None):
    if port is None:
        port = find_available_port()

    server = ThreadingHTTPServer(("127.0.0.1", port), ResearchAgentHandler)
    url = f"http://localhost:{port}"

    print("=" * 64)
    print(f" Super Investing · Research Agent Terminal Web Server")
    print(f" Running at: {url}")
    print(f" Monochrome minimalist UI active. Press Ctrl+C to stop.")
    print("=" * 64)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    run_server(port_arg)
