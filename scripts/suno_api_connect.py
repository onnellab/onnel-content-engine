#!/usr/bin/env python3
"""Loopback-only Suno Platform API-key setup console."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

from short_video_credentials import CredentialError, strict_json
from suno_api_credentials import SunoKeychain, credential_status

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "suno_api_connect.html"
PRIVATE_ROOT = Path.home() / "Library/Application Support/ONNELLAB/content-engine/suno-platform"
SERVICE = "onnellab-suno-connect-v1"


class SetupServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 5

    def __init__(self, store, *, address=("127.0.0.1", 0)):
        if address[0] != "127.0.0.1":
            raise ValueError("loopback_only")
        super().__init__(address, SetupHandler)
        self.csrf = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(24)
        self.instance = secrets.token_urlsafe(24)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.store = store

    def handle_error(self, request, address):
        pass


class SetupHandler(BaseHTTPRequestHandler):
    server_version = "ONNELLAB-Local/1"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.reply(code, {"error": "local_request_rejected"})

    def reply(self, code, payload=None, *, html=None):
        data = html.encode("utf-8") if html is not None else json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8" if html is not None else "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy",
            "default-src 'none'; script-src 'nonce-"+self.server.nonce+"'; style-src 'nonce-"+self.server.nonce+
            "'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; "+
            "navigate-to https://platform.suno.com")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def allowed_host(self):
        hosts = self.headers.get_all("Host", [])
        return (
            self.client_address[0] == "127.0.0.1"
            and hosts == [urlsplit(self.server.origin).netloc]
            and len(self.path) <= 4096
            and self.path.startswith("/")
            and not self.path.startswith("//")
        )

    def authenticated(self, *, mutate=False):
        if not self.allowed_host():
            return False
        origins = self.headers.get_all("Origin", [])
        if origins not in ([self.server.origin], []) or (mutate and not origins):
            return False
        values = self.headers.get_all("X-ONNELLAB-CSRF", [])
        return len(values) == 1 and values[0].isascii() and secrets.compare_digest(values[0], self.server.csrf)

    def do_OPTIONS(self):
        self.reply(403, {"error": "cross_origin_denied"})

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, {"error": "invalid_local_host"})
        path = urlsplit(self.path)
        if path.path == "/favicon.ico" and not path.query:
            return self.reply(204, html="")
        if path.path == "/health" and not path.query:
            return self.reply(200, {"service": SERVICE, "instance": self.server.instance})
        if path.path == "/" and not path.query:
            try:
                page = TEMPLATE.read_text(encoding="utf-8")
            except OSError:
                return self.reply(503, {"error": "setup_page_missing"})
            return self.reply(200, html=page.replace("__NONCE__", self.server.nonce).replace("__CSRF__", self.server.csrf))
        if path.path == "/api/status" and not path.query:
            if not self.authenticated():
                return self.reply(403, {"error": "local_session_required"})
            return self.reply(200, credential_status(store=self.server.store))
        return self.reply(404, {"error": "not_found"})

    def do_POST(self):
        if not self.authenticated(mutate=True):
            return self.reply(403, {"error": "local_session_required"})
        if urlsplit(self.path).query:
            return self.reply(400, {"error": "query_not_allowed"})
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, {"error": "json_required"})
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit() or not 1 <= int(lengths[0]) <= 16384 or self.headers.get("Transfer-Encoding"):
            return self.reply(413, {"error": "request_size_invalid"})
        try:
            data = strict_json(self.rfile.read(int(lengths[0])))
            if self.path == "/api/save":
                if set(data) != {"api_key"}:
                    raise CredentialError("connection_fields_invalid")
                self.server.store.save(data["api_key"])
                return self.reply(200, credential_status(store=self.server.store))
            if self.path == "/api/delete":
                if data != {"confirm": True}:
                    raise CredentialError("disconnect_confirmation_required")
                self.server.store.delete()
                return self.reply(200, credential_status(store=self.server.store))
            if self.path == "/api/close":
                if data:
                    raise CredentialError("connection_fields_invalid")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return self.reply(200, {"state": "closed"})
            return self.reply(404, {"error": "not_found"})
        except CredentialError as exc:
            return self.reply(400, {"error": str(exc)})
        except Exception:
            return self.reply(400, {"error": "local_connection_operation_failed"})


def private_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise CredentialError("unsafe_local_setup_directory")
    os.chmod(path, 0o700)
    return path


def open_console(*, open_browser=True, ttl=7200, private_root=PRIVATE_ROOT):
    if sys.platform != "darwin":
        raise CredentialError("keychain_requires_macos")
    root = private_directory(private_root)
    descriptor = os.open(root / "suno-connect.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    os.fchmod(descriptor, 0o600)
    server = None
    timer = None
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            from urllib.request import build_opener, ProxyHandler
            from short_video_youtube import NoRedirect
            session = root / "suno-connect-session.json"
            if session.is_symlink() or session.stat().st_mode & 0o077:
                raise CredentialError("unsafe_local_setup_session")
            info = strict_json(session.read_bytes())
            port = info.get("port")
            if type(port) is not int or not 1024 <= port <= 65535:
                raise CredentialError("invalid_local_setup_port")
            url = f"http://127.0.0.1:{port}"
            try:
                with build_opener(ProxyHandler({}), NoRedirect).open(url + "/health", timeout=3) as response:
                    check = strict_json(response.read(4096))
                if check != {"service": SERVICE, "instance": info.get("instance")}:
                    raise ValueError()
            except Exception:
                raise CredentialError("local_setup_stale_retry") from None
            if open_browser:
                webbrowser.open(url + "/", new=2)
            return
        server = SetupServer(SunoKeychain(interactive=True))
        session = root / "suno-connect-session.json"
        fd = os.open(session, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"port": server.server_port, "instance": server.instance}, stream)
        timer = threading.Timer(ttl, server.shutdown)
        timer.daemon = True
        timer.start()
        if open_browser:
            webbrowser.open(server.origin + "/", new=2)
        print(json.dumps({"state": "local_setup_open", "expires_in_seconds": ttl}), flush=True)
        server.serve_forever(poll_interval=0.25)
    finally:
        if timer:
            timer.cancel()
        if server:
            server.server_close()
            (root / "suno-connect-session.json").unlink(missing_ok=True)
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["open"])
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        open_console(open_browser=not args.no_browser)
        return 0
    except KeyboardInterrupt:
        return 0
    except CredentialError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}), file=sys.stderr)
        return 2
    except Exception:
        print(json.dumps({"status": "blocked", "error": "local_setup_failed"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
