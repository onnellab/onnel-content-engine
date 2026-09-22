"""HTTP handler tests use byte buffers, not sockets, browsers or real Keychain."""
from __future__ import annotations
import io
import json
from email.message import Message
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlencode, parse_qs, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from short_video_connect import SetupHandler, SetupServer, TEMPLATE
from short_video_oauth import Connection
from short_video_credentials import CredentialError
from install_youtube_connect import applescript_source, URLS, YOUTUBE_URLS, LYRIA_URLS
from youtube_dashboard_panel import youtube_settings_panel
import test_short_video_credentials as fixtures

class LocalConsoleTests(unittest.TestCase):
    def setUp(self):
        self.store=fixtures.MemoryStore()
        self.google=fixtures.FakeGoogle()
        self.server=SimpleNamespace(origin='http://127.0.0.1:49001',csrf='csrf-token',nonce='nonce',
            store=self.store,guard=threading.Lock(),last_result=None,last_error=None,instance='instance',
            flow=Connection(self.store,send=self.google))
    def handler(self,path='/',*,body=None,extra=None):
        h=object.__new__(SetupHandler); h.server=self.server;h.client_address=('127.0.0.1',50000);h.path=path
        h.headers=Message();h.headers['Host']='127.0.0.1:49001'
        h.headers['Origin']=self.server.origin;h.headers['X-ONNELLAB-CSRF']=self.server.csrf
        if extra:
            for key,value in extra.items():
                if key in h.headers: del h.headers[key]
                if value is not None: h.headers[key]=value
        data=json.dumps(body or {}).encode();h.rfile=io.BytesIO(data)
        h.headers['Content-Type']='application/json';h.headers['Content-Length']=str(len(data))
        h.reply=Mock();return h
    def test_root_has_no_credential_values_and_no_cache_storage_code(self):
        h=self.handler();h.do_GET();html=h.reply.call_args.kwargs['html']
        self.assertNotIn('__CSRF__',html);self.assertIn('csrf-token',html)
        for forbidden in ['localStorage','sessionStorage','indexedDB','.innerHTML','DO-NOT-PRINT']:
            self.assertNotIn(forbidden,html)
        self.assertIn("latest={state:'blocked',error:code,last_check:null}",html)
    def test_public_dashboard_is_navigation_only(self):
        html=youtube_settings_panel()
        for url in YOUTUBE_URLS:self.assertIn(url,html)
        self.assertIn(LYRIA_URLS[0],html)
        for bad in ['YOUTUBE_REFRESH_TOKEN','<input','fetch(','localStorage','http://127.0.0.1']:
            self.assertNotIn(bad,html)
        self.assertIn('yt-ko',html);self.assertIn('yt-en',html)
    def test_status_does_not_load_or_refresh_tokens(self):
        self.store.value=fixtures.BUNDLE
        h=self.handler('/api/status');h.do_GET()
        self.assertEqual('configured_not_checked',h.reply.call_args.args[1]['state'])
        self.assertEqual(0,self.store.loads);self.assertEqual([],self.google.calls)
    def test_mutations_reject_cross_origin_missing_csrf_and_rebound_host(self):
        for extra in [{'Origin':'https://evil.test'},{'Origin':'null'},{'Origin':None},
                      {'X-ONNELLAB-CSRF':None},{'X-ONNELLAB-CSRF':'bad'},{'Host':'127.0.0.1.evil.test'},
                      {'Host':'localhost:49001'}]:
            with self.subTest(extra=extra):
                h=self.handler('/api/disconnect',body={'confirm':True},extra=extra);h.do_POST()
                self.assertEqual(403,h.reply.call_args.args[0]);self.assertEqual([],self.google.calls)
    def test_duplicate_host_rejected(self):
        h=self.handler();h.headers['Host']='evil.test';h.do_GET()
        self.assertEqual(403,h.reply.call_args.args[0])
    def test_lan_client_rejected(self):
        h=self.handler();h.client_address=('192.168.1.1',9999);h.do_GET()
        self.assertEqual(403,h.reply.call_args.args[0])
    def test_cors_preflight_is_denied(self):
        h=self.handler('/api/check');h.do_OPTIONS();self.assertEqual(403,h.reply.call_args.args[0])
    def test_secret_input_goes_only_to_in_memory_oauth(self):
        h=self.handler('/api/connect',body={'client_json':fixtures.CLIENT,'channel_id':fixtures.CHANNEL});h.do_POST()
        result=h.reply.call_args.args[1];self.assertEqual(200,h.reply.call_args.args[0])
        self.assertNotIn('DO-NOT-PRINT',json.dumps(result));self.assertEqual(0,self.store.writes)
        self.assertEqual([],self.google.calls)
        params=parse_qs(urlsplit(result['authorization_url']).query)
        self.assertEqual(['S256'],params['code_challenge_method'])
    def test_callback_strips_code_and_verifies_before_save(self):
        url=self.server.flow.begin(fixtures.CLIENT,fixtures.CHANNEL,self.server.origin+'/oauth/callback')
        state=parse_qs(urlsplit(url).query)['state'][0]
        h=self.handler('/oauth/callback?'+urlencode({'code':'SECRET_CODE','state':state}),extra={'Origin':None})
        h.do_GET();self.assertEqual(303,h.reply.call_args.args[0]);self.assertEqual('/',h.reply.call_args.kwargs['location'])
        self.assertNotIn('SECRET_CODE',str(h.reply.call_args));self.assertEqual(1,self.store.writes)
    def test_invalid_callback_never_overwrites_connection(self):
        self.store.value=fixtures.BUNDLE
        self.server.flow.begin(fixtures.CLIENT,fixtures.CHANNEL,self.server.origin+'/oauth/callback')
        h=self.handler('/oauth/callback?state=bad&code=SECRET');h.do_GET()
        self.assertEqual(0,self.store.writes);self.assertEqual('oauth_state_mismatch',self.server.last_error)
    def test_check_and_reconnect_share_store_without_exposing_bundle(self):
        self.store.value=fixtures.BUNDLE
        h=self.handler('/api/check',body={});h.do_POST()
        self.assertTrue(h.reply.call_args.args[1]['channel_verified'])
        self.assertNotIn('DO-NOT-PRINT',str(h.reply.call_args));self.assertEqual(0,self.store.writes)
        h=self.handler('/api/reconnect',body={});h.do_POST()
        self.assertEqual(200,h.reply.call_args.args[0]);self.assertNotIn('DO-NOT-PRINT',str(h.reply.call_args))
    def test_disconnect_requires_explicit_confirmation(self):
        self.store.value=fixtures.BUNDLE
        h=self.handler('/api/disconnect',body={});h.do_POST();self.assertTrue(self.store.present())
        h=self.handler('/api/disconnect',body={'confirm':True});h.do_POST();self.assertFalse(self.store.present())
    def test_wrong_types_sizes_and_arbitrary_action_paths_fail(self):
        h=self.handler('/api/connect',body={'client_json':fixtures.CLIENT,'channel_id':fixtures.CHANNEL,'command':'rm'});h.do_POST()
        self.assertEqual(400,h.reply.call_args.args[0])
        h=self.handler('/api/check');h.headers.replace_header('Content-Length','999999');h.do_POST()
        self.assertEqual(413,h.reply.call_args.args[0])
        h=self.handler('/api/upload');h.do_POST();self.assertEqual(404,h.reply.call_args.args[0])
        h=self.handler('/api/check?secret=x');h.do_POST();self.assertEqual(400,h.reply.call_args.args[0])
        self.assertFalse(self.google.calls)
    def test_response_security_headers(self):
        h=self.handler();h.reply=SetupHandler.reply.__get__(h,SetupHandler)
        h.send_response=Mock();h.send_header=Mock();h.end_headers=Mock();h.wfile=io.BytesIO()
        h.reply(200,{'state':'ok'})
        headers=dict(call.args for call in h.send_header.call_args_list)
        self.assertIn('no-store',headers['Cache-Control']);self.assertEqual('no-referrer',headers['Referrer-Policy'])
        self.assertEqual('DENY',headers['X-Frame-Options']);self.assertNotIn('Access-Control-Allow-Origin',headers)
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
    def test_removed_credentials_clear_previous_verified_status(self):
        self.server.last_result={'state':'connected','channel_title':'Old channel'}
        h=self.handler('/api/status');h.do_GET()
        result=h.reply.call_args.args[1]
        self.assertEqual('not_connected',result['state'])
        self.assertIsNone(result['last_check'])
        self.assertEqual(0,self.store.loads)

    def test_failed_connection_check_clears_stale_green_result(self):
        self.store.value=fixtures.BUNDLE
        h=self.handler('/api/check');h.do_POST()
        self.assertTrue(self.server.last_result['channel_verified'])
        self.google.scope=fixtures.SCOPES[1]
        h=self.handler('/api/check');h.do_POST()
        self.assertEqual(400,h.reply.call_args.args[0])
        self.assertIsNone(self.server.last_result)
        self.assertEqual('youtube_scopes_missing',self.server.last_error)
        self.assertEqual(fixtures.BUNDLE,self.store.value)

    def test_launch_source_accepts_only_exact_fixed_urls(self):
        source=applescript_source('/a path/python','/a path/script.py')
        self.assertIn('on open location targetURL',source)
        for url in URLS:self.assertIn('"'+url+'"',source)
        self.assertIn('launchYouTube',source);self.assertIn('launchLyria',source)
        self.assertIn('lyria_connect.py',source)
        self.assertNotIn('refresh_token',source);self.assertNotIn('client_secret',source)
    def test_non_loopback_server_is_not_created(self):
        with self.assertRaisesRegex(ValueError,'loopback_only'):
            SetupServer(self.store,address=('0.0.0.0',0))

if __name__=='__main__':unittest.main()
