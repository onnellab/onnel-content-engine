"""Excluded channels remain archives and never enter new publication work."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from approve_syndication_draft import approve_syndication_draft, SyndicationApprovalError
from build_manual_publish_site import publishing_mode, compose_url
from check_distribution_supply import REQUIRED_SYNDICATION_PLATFORMS
from generate_syndication_drafts import generate_syndication_drafts, SyndicationError
from post_syndication_drafts import approved_drafts, post_syndication_drafts, SyndicationPostingError
from reconcile_remote_browser_publications import reconcile
from validate_syndication_drafts import validate_draft
from verify_manual_publications import verify_item


class DistributionExclusionTests(unittest.TestCase):
    def test_excluded_channel_cannot_be_generated_or_approved_even_with_old_override(self):
        for platform in ('medium', 'hashnode'):
            with self.subTest(platform=platform):
                with self.assertRaisesRegex(SyndicationError, 'user_excluded'):
                    generate_syndication_drafts(platforms=(platform,))
                with self.assertRaisesRegex(SyndicationApprovalError, 'user_excluded'):
                    approve_syndication_draft('T1', platform, 'en', 'operator', allow_medium=True)
                with self.assertRaisesRegex(SyndicationPostingError, 'user_excluded'):
                    post_syndication_drafts(platform=platform, adapter='mock')
                with self.assertRaisesRegex(SyndicationPostingError, 'user_excluded'):
                    post_syndication_drafts(adapter=platform)

    def test_approved_selector_keeps_devto_but_never_excluded_platforms(self):
        drafts = [{'topic_id': 'T1', 'language': 'en', 'platform': p, 'status': 'approved'}
                  for p in ('medium', 'hashnode', 'devto')]
        self.assertEqual(['devto'], [d['platform'] for d in approved_drafts({'drafts': drafts})])
        self.assertEqual({'devto'}, REQUIRED_SYNDICATION_PLATFORMS)
        for platform in ('medium', 'hashnode'):
            self.assertEqual('disabled', publishing_mode(platform))
            self.assertEqual('', compose_url(platform, '', 'https://onnellab.com/blog/example/'))
        self.assertEqual('remote_browser', publishing_mode('x'))
        self.assertEqual('remote_browser', publishing_mode('linkedin'))

    def test_generation_preserves_all_excluded_drafts_manifests_and_unlisted_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'generated/syndication'
            output.mkdir(parents=True)
            drafts = []
            for platform in ('medium', 'hashnode'):
                for status in ('user_excluded', 'posted'):
                    path = output / f'{platform}-{status}.md'
                    path.write_bytes(b'Historical bytes\r\nDo not rewrite.\n')
                    drafts.append({'topic_id': status, 'platform': platform, 'language': 'en',
                        'draft_path': path.relative_to(root).as_posix(), 'status': status,
                        'posted_url': 'https://example.com/history' if status == 'posted' else ''})
            orphan = output / 'medium/orphan.md'
            orphan.parent.mkdir()
            orphan.write_bytes(b'Unlisted historical draft')
            (output / 'manifest.json').write_text(json.dumps({'drafts': drafts}))
            before = {p: p.read_bytes() for p in output.rglob('*.md')}
            with patch('generate_syndication_drafts.load_publishable_articles', return_value=[]):
                result = generate_syndication_drafts(root / 'topics/topics.csv', output)
            self.assertEqual(drafts, result)
            self.assertEqual(before, {p: p.read_bytes() for p in output.rglob('*.md')})

    def test_excluded_archive_validation_does_not_demand_rewriting_old_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'old.md'
            path.write_text('Untouched old draft')
            validate_draft({'topic_id': 'T1', 'platform': 'medium', 'language': 'en',
                'canonical_url': 'https://onnellab.com/blog/example/', 'draft_path': 'old.md',
                'status': 'user_excluded'}, Path(directory))

    def test_archive_collision_blocks_before_any_output_write(self):
        for relative in ('generated/syndication/devto/en/reading/example.md', 'generated/syndication/manifest.json'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / 'generated/syndication'
                path = root / relative
                path.parent.mkdir(parents=True)
                row = {'topic_id': 'OLD', 'platform': 'medium', 'language': 'en',
                       'draft_path': relative, 'status': 'user_excluded'}
                manifest = output / 'manifest.json'
                if path != manifest:
                    path.write_bytes(b'Excluded source cannot be overwritten')
                manifest.write_text(json.dumps({'drafts': [row]}))
                before = {p: p.read_bytes() for p in output.rglob('*') if p.is_file()}
                article = SimpleNamespace(topic={'primary_language': 'en', 'category': 'reading', 'slug': 'example'})
                with patch('generate_syndication_drafts.load_publishable_articles', return_value=[article]), \
                        self.assertRaisesRegex(SyndicationError, 'conflicts'):
                    generate_syndication_drafts(root / 'topics/topics.csv', output)
                self.assertEqual(before, {p: p.read_bytes() for p in output.rglob('*') if p.is_file()})

    def test_dashboard_schedule_summary_filters_disabled_history(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts/build_manual_publish_site.py').read_text(encoding='utf-8')
        self.assertIn("item.publishing_mode !== 'disabled' && item.status !== 'user_excluded'", source)
        self.assertIn("rows[0]?.publishing_mode === 'disabled' ? null", source)

    def test_verifier_does_not_contact_excluded_channels(self):
        fetch = Mock(side_effect=AssertionError('must not fetch'))
        for platform in ('medium', 'hashnode'):
            self.assertIsNone(verify_item({'platform': platform}, fetch_json=fetch, fetch_text=fetch))
        fetch.assert_not_called()

    def test_excluded_new_receipt_is_preserved_without_blocking_x_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            social, synd, inbox, state = [root / (name + '.json') for name in ('social', 'synd', 'inbox', 'state')]
            social.write_text(json.dumps({'posts': [{'topic_id': 'T1', 'platform': 'x', 'language': 'en', 'template_id': 'x'}]}))
            synd.write_text(json.dumps({'drafts': []}))
            excluded = {'manual_key': 'T2::medium::en::markdown', 'platform': 'medium',
                'posted_url': 'https://medium.com/@onnellab/old-abcdef', 'status': 'new'}
            inbox.write_text(json.dumps({'schema_version': 1, 'records': [excluded, {
                'manual_key': 'T1::x::en::x', 'platform': 'x', 'posted_url': 'https://x.com/onnellab/status/123', 'status': 'new'}]}))
            old = {'posted_url': 'https://medium.com/@onnellab/history-123abc', 'marked_at': 'old'}
            state.write_text(json.dumps({'done': {'old::medium::en::markdown': old}}))
            self.assertEqual(1, reconcile(inbox, state, social, synd))
            self.assertEqual(excluded, json.loads(inbox.read_text())['records'][0])
            self.assertEqual(old, json.loads(state.read_text())['done']['old::medium::en::markdown'])


if __name__ == '__main__':
    unittest.main()
