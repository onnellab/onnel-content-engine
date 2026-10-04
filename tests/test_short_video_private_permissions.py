"""Read-only ACL policy and offline pre-initiation upload protection tests."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from short_video_pipeline import digest, file_hash
from short_video_private_permissions import private_dacl, private_path_permissions
import short_video_private_permissions as permissions
from short_video_youtube import Uploader


def sanitized_acl_diagnostic(path):
    """Test failure context only: never return identifiers, paths or messages."""
    if os.name != 'nt':
        return {'platform': 'posix'}
    try:
        owner, current, entries = permissions._windows_security(path)
    except (OSError, ValueError) as exc:
        return {'inspection_error_type': type(exc).__name__,
                'winerror': getattr(exc, 'winerror', None),
                'errno': getattr(exc, 'errno', None)}

    def principal(sid):
        if sid == current:
            return 'current_user'
        return {'S-1-5-18': 'system', 'S-1-5-32-544': 'administrators',
                'S-1-3-4': 'owner_rights'}.get(sid, 'other')

    def rights(mask):
        categories = []
        for label, bits in [('generic', 0xF0000000), ('read', 0x89),
                            ('write', 0x116), ('execute', 0x20),
                            ('delete', 0x10040), ('security_control', 0xE0000),
                            ('synchronize', 0x100000)]:
            if mask & bits:
                categories.append(label)
        return categories

    return {'owner_current': owner == current, 'owner_builtin_kind': principal(owner),
            'null_dacl': entries is None,
            'aces': [{'type': kind, 'principal': principal(sid), 'rights': rights(mask)}
                     for kind, mask, sid in (entries or [])]}


class PrivatePermissionTests(unittest.TestCase):
    def test_acl_diagnostics_never_expose_identifiers_or_exception_messages(self):
        secret = 'private-identifier-path-and-message'
        with patch.object(os, 'name', 'nt'), \
                patch.object(permissions, '_windows_security',
                             return_value=('S-1-5-32-544', secret, [(0, 0x1F01FF, secret)])):
            result = sanitized_acl_diagnostic(secret)
        self.assertFalse(result['owner_current'])
        self.assertEqual('administrators', result['owner_builtin_kind'])
        self.assertEqual('current_user', result['aces'][0]['principal'])
        self.assertNotIn(secret, repr(result))
        self.assertNotIn('S-1-', repr(result))
        with patch.object(os, 'name', 'nt'), \
                patch.object(permissions, '_windows_security', side_effect=OSError(5, secret)):
            result = sanitized_acl_diagnostic(secret)
        self.assertEqual({'inspection_error_type': 'OSError', 'winerror': None, 'errno': 5}, result)
        self.assertNotIn(secret, repr(result))

    def test_windows_owner_system_admin_and_owner_rights_are_private(self):
        user = 'S-1-5-21-1-2-3-1001'
        entries = [(0, 0x1F01FF, sid) for sid in (user, 'S-1-5-18', 'S-1-5-32-544', 'S-1-3-4')]
        self.assertTrue(private_dacl(user, user, entries))
        self.assertTrue(private_dacl(user, user, entries + [(1, 1, 'S-1-1-0')]))

    def test_broad_foreign_unknown_and_null_acls_fail_closed(self):
        user = 'S-1-5-21-1-2-3-1001'
        for sid in ('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545', 'S-1-5-21-9-8-7-1001'):
            for mask in (1, 2, 4, 0x40, 0x10000, 0x80000000, 0x40000000, 0x10000000, 0x40000, 0x80000):
                with self.subTest(principal=sid, access=mask):
                    self.assertFalse(private_dacl(user, user, [(0, mask, sid)]))
        self.assertFalse(private_dacl(user, user, None))
        self.assertFalse(private_dacl(user, 'different-user', [(0, 1, user)]))
        self.assertFalse(private_dacl(user, user, [(9, 1, user)]))

    def test_builtin_owned_private_dacl_matches_hosted_windows_fixture(self):
        user = 'S-1-5-21-1-2-3-1001'
        # Hosted Python 3.14 mode0700: Admin owner, SYSTEM/Admin/OWNER RIGHTS.
        entries = [(0, 0x1F01FF, sid) for sid in ('S-1-5-18', 'S-1-5-32-544', 'S-1-3-4')]
        for owner in (user, 'S-1-5-18', 'S-1-5-32-544'):
            with self.subTest(owner=owner):
                self.assertTrue(private_dacl(owner, user, entries))
                self.assertTrue(private_dacl(owner, user, entries + [(0, 0x1F01FF, user)]))
                for current in (None, ''):
                    self.assertFalse(private_dacl(owner, current, entries))
                self.assertFalse(private_dacl(owner, user, None))
                self.assertFalse(private_dacl(owner, user, entries + [(9, 0, user)]))
                for foreign in ('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545', 'S-1-5-21-9-8-7-1001'):
                    for access in (1, 2, 0x10000, 0x40000, 0x80000):
                        self.assertFalse(private_dacl(owner, user, entries + [(0, access, foreign)]))
        for owner in (None, '', 'S-1-3-4', 'S-1-1-0', 'S-1-5-32-545', 'S-1-5-21-9-8-7-1001'):
            with self.subTest(untrusted_owner=owner):
                self.assertFalse(private_dacl(owner, user, entries))

    def test_existing_private_fixture_is_readable_without_acl_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fd, name = tempfile.mkstemp(dir=root)
            os.close(fd)
            for path in (root, Path(name)):
                if not private_path_permissions(path):
                    self.fail(f'Private fixture rejected: {sanitized_acl_diagnostic(path)}')
            self.assertFalse(private_path_permissions(root / 'missing'))

    @unittest.skipUnless(os.name != 'nt', 'POSIX mode bits apply only on POSIX')
    def test_posix_group_readable_file_remains_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'fixture'
            path.write_text('fixture only')
            path.chmod(0o600)
            self.assertTrue(private_path_permissions(path))
            path.chmod(0o640)
            self.assertFalse(private_path_permissions(path))

    @unittest.skipUnless(os.name == 'nt', 'Windows ACL inspection only')
    def test_windows_inspection_failure_blocks_instead_of_trusting_mode_bits(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch('short_video_private_permissions._windows_security', side_effect=OSError('uninspectable')):
            self.assertFalse(private_path_permissions(Path(tmp)))

    def test_unverified_parent_blocks_before_factory_or_insert(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobdir = root / 'jobs' / 'fixture-id'
            jobdir.mkdir(parents=True, mode=0o700)
            video = jobdir / 'video.mp4'
            video.write_bytes(b'fixture only')
            hashed = file_hash(video)
            job = {'id': 'fixture-id', 'status': 'rendered', 'brief': {}, 'payload_hash': 'payload',
                   'result': {'sha256': {'video.mp4': hashed}},
                   'approval': {'render_hash': hashed, 'payload_hash': 'payload',
                                'mode': 'manual', 'choices': {}, 'metadata_hash': digest({})}}
            state = {'jobs': {job['id']: job}}
            q = Mock(root=root, state_path=root / 'queue.json')
            q.clock.return_value = datetime.now(timezone.utc)
            factory = Mock(side_effect=AssertionError('must not load credentials or call API'))
            uploader = Uploader(q, factory)
            with patch.object(uploader, 'artifact', return_value=video), \
                    patch('short_video_youtube.metadata', return_value={}), \
                    patch('short_video_youtube.private_path_permissions', return_value=False):
                result = uploader.run_locked(state, job)
            self.assertEqual('blocked', result['status'])
            self.assertEqual('unsafe_session_parent_permissions', result['error'])
            self.assertNotIn('upload', result)
            factory.assert_not_called()
            self.assertFalse((jobdir / 'youtube-session.json').exists())


if __name__ == '__main__':
    unittest.main()
