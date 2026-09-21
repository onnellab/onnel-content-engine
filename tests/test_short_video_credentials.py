"""OAuth and credential tests are offline and never use the user's Keychain."""
from __future__ import annotations
import copy
import hashlib
import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_credentials import (CredentialError, MacKeychain, NAMES, SCOPES, credential_status,
    resolve_credentials, validate_bundle, strict_json)
from short_video_oauth import Connection, OAuthError, AUTH, TOKEN, CHANNELS, desktop_client, local_redirect
from short_video_youtube import YouTube

CHANNEL = 'UC' + 'a' * 22
CLIENT = json.dumps({'installed': {'client_id': 'example.apps.googleusercontent.com',
    'client_secret': 'DO-NOT-PRINT-SECRET', 'auth_uri': AUTH, 'token_uri': TOKEN}})
REDIRECT = 'http://127.0.0.1:49001/oauth/callback'
BUNDLE = dict(schema_version=1, client_id='example.apps.googleusercontent.com',
    client_secret='DO-NOT-PRINT-SECRET', refresh_token='DO-NOT-PRINT-REFRESH', channel_id=CHANNEL,
    channel_title='ONNELLAB', scopes=list(SCOPES), verified_at='2026-09-21T08:00:00Z')

class MemoryStore:
    def __init__(self, value=None): self.value=copy.deepcopy(value); self.loads=0; self.writes=0
    def present(self): return self.value is not None
    def load(self):
        self.loads += 1
        if self.value is None: raise CredentialError('missing_youtube_credentials')
        return copy.deepcopy(self.value)
    def save(self, value): self.value=copy.deepcopy(validate_bundle(value)); self.writes+=1
    def delete(self): self.value=None

class FakeGoogle:
    def __init__(self):
        self.calls=[]; self.expected=CHANNEL; self.code=200; self.scope=' '.join(SCOPES)
        self.refresh='DO-NOT-PRINT-REFRESH'; self.items=None; self.kind='Bearer'
    def __call__(self, method, url, headers, body):
        self.calls.append((method,url,headers,body))
        if url==TOKEN:
            result={'access_token':'DO-NOT-PRINT-ACCESS','token_type':self.kind,'scope':self.scope}
            if self.refresh: result['refresh_token']=self.refresh
        else:
            result={'items': self.items if self.items is not None else [{'id':self.expected,'snippet':{'title':'ONNELLAB'}}]}
        return self.code, {}, json.dumps(result).encode()

class CredentialTests(unittest.TestCase):
    def test_bundle_is_atomic_and_complete(self):
        for key in BUNDLE:
            value=copy.deepcopy(BUNDLE); del value[key]
            with self.subTest(key=key), self.assertRaises(CredentialError): validate_bundle(value)
    def test_provider_keychain_first_and_no_environment_mixing(self):
        store=MemoryStore(BUNDLE)
        result=resolve_credentials(store=store,environ={'YOUTUBE_CHANNEL_ID':'foreign'})
        self.assertEqual(CHANNEL,result['YOUTUBE_CHANNEL_ID'])
        self.assertEqual(set(NAMES),set(result))
    def test_locked_keychain_does_not_fall_back_to_env(self):
        store=Mock(); store.load.side_effect=CredentialError('keychain_locked_or_access_denied')
        env=dict(zip(NAMES,['id','secret','refresh',CHANNEL]))
        with self.assertRaisesRegex(CredentialError,'keychain_locked'):
            resolve_credentials(store=store,environ=env)
    def test_environment_is_explicit_opt_in(self):
        store=Mock(side_effect=AssertionError('keychain'))
        env=dict(zip(NAMES,['id','secret','refresh',CHANNEL]))
        env['ONNELLAB_YOUTUBE_CREDENTIAL_SOURCE']='environment'
        self.assertEqual(CHANNEL,resolve_credentials(store=store,environ=env)['YOUTUBE_CHANNEL_ID'])
        store.load.assert_not_called()
        del env[NAMES[0]]
        with self.assertRaises(CredentialError): resolve_credentials(store=store,environ=env)
    def test_readiness_is_attribute_only_no_secret_load(self):
        store=MemoryStore(BUNDLE)
        status=credential_status(store=store,environ={})
        self.assertTrue(status['configured']); self.assertFalse(status['network_verified']); self.assertEqual(0,store.loads)
        self.assertNotIn('DO-NOT',json.dumps(status))
    def test_readiness_sanitizes_locked_error(self):
        store=Mock(); store.present.side_effect=CredentialError('keychain_locked_or_access_denied')
        result=credential_status(store=store,environ={})
        self.assertFalse(result['configured']); self.assertEqual(list(NAMES),result['missing'])
    def test_worker_constructor_uses_shared_provider(self):
        env=resolve_credentials(store=MemoryStore(BUNDLE),environ={})
        with patch('short_video_youtube.resolve_credentials',return_value=env) as resolve:
            api=YouTube(send=FakeGoogle())
        resolve.assert_called_once(); self.assertEqual(CHANNEL,api.channel)
    def test_worker_explicit_env_does_not_read_keychain(self):
        env=resolve_credentials(store=MemoryStore(BUNDLE),environ={})
        with patch('short_video_youtube.resolve_credentials',side_effect=AssertionError('keychain')):
            YouTube(env=env,send=FakeGoogle()).verify()
    def test_native_status_codes_are_safe(self):
        for code,expected in [(-25300,'missing_youtube_credentials'),(-25308,'keychain_locked_or_access_denied'),(-1,'keychain_operation_failed')]:
            with self.subTest(code=code),self.assertRaisesRegex(CredentialError,expected): MacKeychain._check(code)
    def test_duplicate_or_invalid_json_fails_closed(self):
        for raw in ['{"a":1,"a":2}','[1]','{"a":NaN}','x'*33000]:
            with self.subTest(raw=raw[:16]),self.assertRaises(CredentialError): strict_json(raw)

class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.store=MemoryStore(BUNDLE); self.google=FakeGoogle(); self.now=100
        self.c=Connection(self.store,send=self.google,clock=lambda:self.now)
    def begin(self):
        url=self.c.begin(CLIENT,CHANNEL,REDIRECT)
        self.fields=parse_qs(urlsplit(url).query)
        return self.fields
    def callback(self,**overrides):
        args={'state':self.fields['state'][0],'code':'ONE-TIME-CODE'}; args.update(overrides)
        return self.c.complete(urlencode(args))
    def test_pkce_and_minimal_scopes(self):
        fields=self.begin(); p=self.c.pending
        expected=base64.urlsafe_b64encode(hashlib.sha256(p['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual([expected],fields['code_challenge'])
        self.assertEqual(['S256'],fields['code_challenge_method'])
        self.assertEqual(set(SCOPES),set(fields['scope'][0].split()))
        self.assertEqual(['offline'],fields['access_type'])
        self.assertNotIn('client_secret',fields)
    def test_success_checks_expected_channel_before_atomic_save(self):
        self.begin(); result=self.callback()
        self.assertEqual(1,self.store.writes); self.assertTrue(result['channel_verified'])
        self.assertFalse(result['public_upload_verified']); self.assertEqual(CHANNEL,result['channel_id'])
        self.assertNotIn('DO-NOT',json.dumps(result))
        self.assertEqual([TOKEN,CHANNELS],[call[1] for call in self.google.calls])
        post=parse_qs(self.google.calls[0][3].decode()); self.assertIn('code_verifier',post)
    def test_wrong_state_no_network_or_overwrite(self):
        self.begin()
        with self.assertRaisesRegex(OAuthError,'state_mismatch'): self.callback(state='wrong')
        self.assertEqual([],self.google.calls); self.assertEqual(0,self.store.writes)
    def test_state_is_one_use(self):
        self.begin(); self.callback()
        with self.assertRaisesRegex(OAuthError,'missing_or_used'): self.callback()
    def test_expired_state_fails_and_consumes(self):
        self.begin(); self.now+=601
        with self.assertRaisesRegex(OAuthError,'session_expired'): self.callback()
        self.assertIsNone(self.c.pending); self.assertFalse(self.google.calls)
    def test_denial_preserves_old_connection(self):
        self.begin()
        with self.assertRaisesRegex(OAuthError,'consent_denied'): self.callback(error='access_denied')
        self.assertEqual(BUNDLE,self.store.value); self.assertEqual(0,self.store.writes)
    def test_missing_scope_or_refresh_or_bad_token_type_preserve_old(self):
        for field,value,reason in [('scope',SCOPES[0],'scopes_missing'),('refresh',None,'offline_access_missing'),('kind','MAC','token_type_invalid')]:
            with self.subTest(field=field):
                self.google=FakeGoogle(); setattr(self.google,field,value); self.c.send=self.google; self.begin()
                with self.assertRaisesRegex(OAuthError,reason): self.callback()
                self.assertEqual(0,self.store.writes); self.assertEqual(BUNDLE,self.store.value)
    def test_foreign_empty_or_multiple_channels_never_save(self):
        for items in [[],[{'id':'UC'+'b'*22}],[{'id':CHANNEL},{'id':CHANNEL}]]:
            self.google.items=items; self.begin()
            with self.assertRaisesRegex(OAuthError,'channel_mismatch'): self.callback()
            self.assertEqual(0,self.store.writes)
    def test_redirect_or_error_response_is_not_followed(self):
        for code in [302,307,400,403,429,503]:
            self.google.code=code; self.begin()
            with self.subTest(code=code),self.assertRaises(OAuthError): self.callback()
            self.assertEqual(0,self.store.writes)
    def test_callback_duplicate_parameter_rejected(self):
        self.begin()
        with self.assertRaisesRegex(OAuthError,'callback_invalid'):
            self.c.complete(urlencode({'state':self.fields['state'][0],'code':'code'})+'&code=other')
        self.assertEqual([],self.google.calls)
    def test_untrusted_imports_and_non_loopback_redirect_rejected(self):
        for doc in [{'web':{}},{'installed':{'client_id':'evil','client_secret':'s'}},
                    {'installed':{'client_id':'x.apps.googleusercontent.com','client_secret':'s','token_uri':'https://evil.test/'}}]:
            with self.assertRaises(CredentialError): desktop_client(json.dumps(doc))
        for url in ['http://localhost:1234/oauth/callback','http://127.0.0.1.evil:80/oauth/callback','https://127.0.0.1:1234/oauth/callback',REDIRECT+'?x=1']:
            with self.assertRaises(OAuthError): local_redirect(url)
    def test_check_does_not_replace_credentials_and_disconnect_removes_only_local(self):
        status=self.c.check(); self.assertTrue(status['channel_verified']); self.assertEqual(0,self.store.writes)
        result=self.c.disconnect(); self.assertFalse(self.store.present()); self.assertFalse(result['google_grant_revoked'])
    def test_storage_failure_never_reports_connected(self):
        self.store.save=Mock(side_effect=CredentialError('keychain_locked_or_access_denied')); self.begin()
        with self.assertRaisesRegex(CredentialError,'keychain_locked'): self.callback()
        self.assertEqual(BUNDLE,self.store.value)

if __name__=='__main__': unittest.main()
