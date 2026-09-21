#!/usr/bin/env python3
"""Temporary, loopback-only YouTube setup console. No web-accessible worker endpoint."""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

from short_video_credentials import CredentialError, MacKeychain, strict_json, SETUP_SCOPES
from youtube_profiles import profile_id, PROFILES as LABELS
from short_video_oauth import Connection, OAuthError, AUTH
from short_video_pipeline import VideoError
import youtube_report_store

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates/youtube_connect.html'
PRIVATE_ROOT = Path.home() / 'Library/Application Support/ONNELLAB/content-engine'
SERVICE = 'onnellab-youtube-connect-v1'


class SetupServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 5
    def __init__(self, store, *, address=('127.0.0.1', 0), connection=None, profile='onnellab', reporting_root=youtube_report_store.ROOT):
        if address[0] != '127.0.0.1': raise ValueError('loopback_only')
        super().__init__(address, SetupHandler)
        self.reporting_root = reporting_root
        self.profile = profile_id(profile)
        self.csrf = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(24)
        self.instance = secrets.token_urlsafe(24)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.store = store
        self.flow = connection if connection is not None else Connection(store, profile=self.profile, scopes=SETUP_SCOPES)
        self.guard = threading.Lock()
        self.last_result = None
        self.last_error = None
        self.serving = threading.Event()
        self.root_server = self
        self.brand_servers = {self.profile:self}
        self.brand_guard = threading.Lock()
    def brand_console(self, profile):
        profile = profile_id(profile)
        with self.brand_guard:
            if profile not in self.brand_servers:
                child = SetupServer(MacKeychain(account=profile, interactive=True), profile=profile, reporting_root=self.reporting_root)
                child.root_server = self.root_server
                child.brand_servers = self.brand_servers
                child.brand_guard = self.brand_guard
                self.brand_servers[profile] = child
                threading.Thread(target=child.serve_forever, daemon=True).start()
                if not child.serving.wait(2): raise OAuthError("local_brand_start_failed")
            return self.brand_servers[profile].origin
    def serve_forever(self, poll_interval=0.25):
        self.serving.set()
        try: super().serve_forever(poll_interval)
        finally: self.serving.clear()
    def close_brands(self):
        for server in list(self.brand_servers.values()):
            server.flow.pending = None
            if server.serving.is_set(): server.shutdown()
            server.server_close()
    def handle_error(self, request, address):
        # Never print exception context containing callback queries or request bodies.
        pass


class SetupHandler(BaseHTTPRequestHandler):
    server_version = 'ONNELLAB-Local/1'
    sys_version = ''
    def setup(self):
        super().setup()
        self.connection.settimeout(10)
    def log_message(self, *args):
        pass
    def send_error(self, code, message=None, explain=None):
        self.reply(code, {'error': 'local_request_rejected'})
    def reply(self, code, payload=None, *, html=None, location=None):
        data = html.encode('utf-8') if html is not None else json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if html is not None else 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'nonce-"+self.server.nonce+"'; style-src 'nonce-"+self.server.nonce+"'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header('Connection', 'close')
        if location: self.send_header('Location', location)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True
    def allowed_host(self):
        hosts=self.headers.get_all('Host', [])
        return (self.client_address[0] == '127.0.0.1' and hosts == [urlsplit(self.server.origin).netloc]
                and len(self.path) <= 16384 and self.path.startswith('/') and not self.path.startswith('//'))
    def authenticated(self, *, mutate=False):
        if not self.allowed_host(): return False
        origins=self.headers.get_all('Origin', [])
        if origins not in ([self.server.origin], []) or (mutate and not origins): return False
        values=self.headers.get_all('X-ONNELLAB-CSRF', [])
        if len(values)!=1 or not values[0].isascii(): return False
        return secrets.compare_digest(values[0],self.server.csrf)
    def do_OPTIONS(self): self.reply(403, {'error':'cross_origin_denied'})
    def do_GET(self):
        if not self.allowed_host(): return self.reply(403, {'error':'invalid_local_host'})
        path=urlsplit(self.path)
        if path.path == '/favicon.ico' and not path.query:
            return self.reply(204, html='')
        if path.path == '/health' and not path.query:
            return self.reply(200, {'service':SERVICE,'instance':self.server.instance})
        if path.path == '/' and not path.query:
            try: page=TEMPLATE.read_text(encoding='utf-8')
            except OSError: return self.reply(503, {'error':'setup_page_missing'})
            return self.reply(200, html=page.replace('__NONCE__',self.server.nonce).replace('__CSRF__',self.server.csrf).replace('__PROFILE_LABEL__',LABELS[getattr(self.server, 'profile', 'onnellab')]).replace('__PROFILE_ID__',getattr(self.server, 'profile', 'onnellab')))
        if path.path == '/api/status' and not path.query:
            if not self.authenticated(): return self.reply(403, {'error':'local_session_required'})
            with self.server.guard:
                try:
                    configured=self.server.store.present()
                    if not configured: self.server.last_result=None
                    state='configured_not_checked' if configured else 'not_connected'
                    result={'state':state, 'last_check':self.server.last_result, 'error':self.server.last_error}
                except CredentialError as exc:
                    self.server.last_result=None
                    result={'state':'blocked','error':str(exc)}
            return self.reply(200,result)
        if path.path == '/api/report' and not path.query:
            if not self.authenticated(): return self.reply(403, {'error':'local_session_required'})
            try:
                if not self.server.store.present():
                    youtube_report_store.clear(self.server.profile, self.server.reporting_root)
                    return self.reply(200, {'report':None})
                return self.reply(200, {'report':youtube_report_store.read(self.server.profile, self.server.reporting_root)})
            except (VideoError,OSError):
                return self.reply(400, {'error':'private_report_unavailable'})
        if path.path == '/oauth/callback':
            with self.server.guard:
                try:
                    self.server.last_result=self.server.flow.complete(path.query)
                    if hasattr(self.server,'reporting_root'): youtube_report_store.clear(self.server.profile,self.server.reporting_root)
                    self.server.last_error=None
                except CredentialError as exc:
                    self.server.last_result=None
                    self.server.last_error=str(exc)
                except Exception:
                    self.server.last_result=None
                    self.server.last_error='oauth_callback_failed'
            # Remove the authorization code/query from the address bar; never echo it.
            return self.reply(303, location='/')
        return self.reply(404, {'error':'not_found'})
    def do_POST(self):
        if not self.authenticated(mutate=True): return self.reply(403, {'error':'local_session_required'})
        if urlsplit(self.path).query: return self.reply(400, {'error':'query_not_allowed'})
        if self.headers.get_content_type() != 'application/json': return self.reply(415, {'error':'json_required'})
        lengths=self.headers.get_all('Content-Length', [])
        if (len(lengths)!=1 or not lengths[0].isdigit() or not 1 <= int(lengths[0]) <= 32768
                or self.headers.get('Transfer-Encoding')):
            return self.reply(413, {'error':'request_size_invalid'})
        try:
            body=self.rfile.read(int(lengths[0])); data=strict_json(body)
            with self.server.guard:
                if self.path == '/api/connect':
                    if set(data)!={'client_json','channel_id'}: raise OAuthError('connection_fields_invalid')
                    url=self.server.flow.begin(data['client_json'],data['channel_id'],self.server.origin+'/oauth/callback')
                    self.server.last_error=None
                    result={'authorization_url':url}
                elif self.path == '/api/reconnect':
                    if data: raise OAuthError('connection_fields_invalid')
                    bundle=self.server.store.load()
                    client=json.dumps({'installed':{'client_id':bundle['client_id'],'client_secret':bundle['client_secret']}})
                    url=self.server.flow.begin(client,bundle['channel_id'],self.server.origin+'/oauth/callback')
                    self.server.last_error=None
                    result={'authorization_url':url}
                elif self.path == '/api/brand':
                    if set(data) != {'profile'} or data['profile'] not in ('onnellab','aether_inn'):
                        raise OAuthError('invalid_brand_profile')
                    result={'local_url':self.server.brand_console(data['profile'])}
                elif self.path == '/api/report-sync':
                    if data: raise OAuthError('connection_fields_invalid')
                    try: result={'report':youtube_report_store.sync(self.server.profile, self.server.reporting_root)}
                    except (VideoError,OSError): raise OAuthError('private_report_sync_failed') from None
                elif self.path == '/api/check':
                    if data: raise OAuthError('connection_fields_invalid')
                    result=self.server.flow.check()
                    self.server.last_result=result; self.server.last_error=None
                elif self.path == '/api/disconnect':
                    if data!={'confirm':True}: raise OAuthError('disconnect_confirmation_required')
                    result=self.server.flow.disconnect()
                    if hasattr(self.server, 'reporting_root'): youtube_report_store.clear(self.server.profile, self.server.reporting_root)
                    self.server.last_result=None; self.server.last_error=None
                elif self.path == '/api/close':
                    if data: raise OAuthError('connection_fields_invalid')
                    result={'state':'closed'}
                    threading.Thread(target=self.server.root_server.shutdown,daemon=True).start()
                else:
                    return self.reply(404, {'error':'not_found'})
            return self.reply(200,result)
        except CredentialError as exc:
            # Replace an old successful check with a failure, not a stale green badge.
            self.server.last_result=None
            self.server.last_error=str(exc)
            return self.reply(400, {'error':str(exc)})
        except Exception:
            self.server.last_result=None
            self.server.last_error='local_connection_operation_failed'
            return self.reply(400, {'error':'local_connection_operation_failed'})


def private_directory(path):
    path=Path(path)
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink() or path.stat().st_uid != os.getuid(): raise CredentialError('unsafe_local_setup_directory')
    os.chmod(path,0o700)
    return path


def open_console(*, open_browser=True, ttl=1200, private_root=PRIVATE_ROOT, profile="onnellab"):
    profile = profile_id(profile)
    if sys.platform!='darwin': raise CredentialError('keychain_requires_macos')
    root=private_directory(Path(private_root) / ("youtube-"+profile))
    descriptor=os.open(root/'youtube-connect.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    os.fchmod(descriptor,0o600)
    server=None; timer=None
    try:
        try: fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            # This file is private and contains only a loopback port + instance ID.
            from urllib.request import build_opener, ProxyHandler
            from short_video_youtube import NoRedirect
            path=root/'youtube-connect-session.json'
            if path.is_symlink() or path.stat().st_mode & 0o077: raise CredentialError('unsafe_local_setup_session')
            info=strict_json(path.read_bytes())
            port=info.get('port')
            if type(port) is not int or not 1024<=port<=65535: raise CredentialError('invalid_local_setup_port')
            url=f'http://127.0.0.1:{port}'
            try:
                with build_opener(ProxyHandler({}),NoRedirect).open(url+'/health',timeout=3) as response:
                    check=strict_json(response.read(4096))
                if check!={'service':SERVICE,'instance':info.get('instance')}: raise ValueError()
            except Exception: raise CredentialError('local_setup_stale_retry') from None
            if open_browser: webbrowser.open(url+'/',new=2)
            return
        server=SetupServer(MacKeychain(account=profile, interactive=True), profile=profile)
        session=root/'youtube-connect-session.json'
        fd=os.open(session,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as stream: json.dump({'port':server.server_port,'instance':server.instance},stream)
        timer=threading.Timer(ttl,server.shutdown); timer.daemon=True; timer.start()
        if open_browser: webbrowser.open(server.origin+'/',new=2)
        print(json.dumps({'state':'local_setup_open','expires_in_seconds':ttl}),flush=True)
        server.serve_forever(poll_interval=0.25)
    finally:
        if timer: timer.cancel()
        if server:
            server.close_brands()
            (root/'youtube-connect-session.json').unlink(missing_ok=True)
        os.close(descriptor)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['open'])
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--profile', choices=['onnellab','aether_inn'], default='onnellab')
    args=parser.parse_args()
    def stop(_signum,_frame): raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    try:
        open_console(open_browser=not args.no_browser, profile=args.profile)
        return 0
    except KeyboardInterrupt: return 0
    except CredentialError as exc:
        print(json.dumps({'status':'blocked','error':str(exc)}),file=sys.stderr); return 2
    except Exception:
        print(json.dumps({'status':'blocked','error':'local_setup_failed'}),file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
