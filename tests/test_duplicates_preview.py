"""Closed manual music comparison preview; no publication or source mutation."""
import copy
import csv
import hashlib
import json
import re
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_duplicates_preview as preview
import prepare_blog_preview as overlay
import select_blog_preview as selector


class ClosedContract(unittest.TestCase):
    def test_profile_has_exact_neutral_source_and_related_links(self):
        profile = overlay.candidate_profile(preview.SLUG)
        self.assertEqual(profile['category'], 'music')
        self.assertIsNone(profile['app_path'])
        self.assertEqual(profile['store_urls'], [])
        self.assertEqual(profile['source_urls'], ['https://musicbrainz.org/doc/Recording'])
        self.assertEqual(profile['faq_count'], 3)
        for locale in preview.LOCALES:
            links = overlay.allowed_candidate_links(preview.SLUG, locale)
            self.assertEqual(links, {
                'https://musicbrainz.org/doc/Recording',
                f'/blog-assets/{locale}/{preview.SLUG}/workflow-diagram.svg',
                f'https://onnellab.com/blog/{locale.lower()}/consistent-album-artist-names/',
                f'https://onnellab.com/blog/{locale.lower()}/organize-local-music-library-offline-android/',
            })
            self.assertEqual(profile['table_rows'][locale], 3)

    def test_exact_native_paths_and_gates_unchanged(self):
        self.assertEqual(preview.GATES, (
            ('validate_topics.py',), ('validate_foundation.py',),
            ('evaluate_all_articles.py',), ('check_nine_language_publication.py',),
            ('check_content_supply.py', '--require-healthy', '--minimum-ideas', '8')))
        paths = preview.native_output_paths()
        self.assertEqual(len(paths), 72)
        self.assertEqual(len(set(paths)), 72)
        self.assertTrue(all(path.startswith('generated/') and preview.SLUG in path for path in paths))
        self.assertFalse(any('privacy' in path or 'social/manifest' in path for path in paths))

    def test_native_manifest_rejects_missing_extra_duplicate_and_hash(self):
        manifest = dict(schema=1, slug=preview.SLUG, locales=list(preview.LOCALES),
                        files=[preview.native_entry(p, b'fixture') for p in preview.native_output_paths()])
        preview.validate_native_manifest(manifest)
        for mode in ('missing', 'extra', 'duplicate', 'hash', 'locale', 'traversal'):
            bad = copy.deepcopy(manifest)
            if mode == 'missing': bad['files'].pop()
            elif mode == 'extra': bad['files'].append(bad['files'][0])
            elif mode == 'duplicate': bad['files'][-1] = bad['files'][0]
            elif mode == 'hash': bad['files'][0]['sha256'] = 'bad'
            elif mode == 'locale': bad['locales'][0] = 'ko'
            else: bad['files'][0]['path'] = '../outside'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                preview.validate_native_manifest(bad)

    def idea(self):
        return dict(id='TOPIC-0087', slug=preview.SLUG, primary_language='en',
                    category='music', status='idea', review_required='true',
                    scheduled_at='', published_at='', published_url='')

    def test_draft_selection_requires_available_source_and_exact_identity(self):
        row = self.idea()
        result = selector.selection_environment([row], ref="refs/heads/main", event="push", duplicates_available=True)
        self.assertIn('DUPLICATES_PREVIEW=true', result)
        self.assertIn('UNCERTAINTY_PREVIEW=false', result)
        with self.assertRaises(ValueError):
            selector.selection_environment([row], duplicates_available=False)
        for key, value in [('id', 'TOPIC-9999'), ('status', 'published'),
                           ('category', 'research'), ('scheduled_at', '2026-11-08')]:
            bad = dict(row, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                selector.selection_environment([bad], ref="refs/heads/main", event="push", duplicates_available=True)

    def test_registered_review_is_dateless_and_published_not_selected(self):
        rows=[]
        for locale, topic_id in preview.REGISTERED_IDS.items():
            row = self.idea()
            row.update(id=topic_id, primary_language=locale, status='review',
                       canonical_path=f'generated/markdown/{locale}/music/{preview.SLUG}.md')
            rows.append(row)
        self.assertEqual(selector.duplicates_state(rows), 'review')
        bad=copy.deepcopy(rows); bad[0]['published_at']='2026-11-08T09:00:00+09:00'
        with self.assertRaises(ValueError): selector.duplicates_state(bad)
        for row in rows:
            row.update(status='published', scheduled_at='2026-11-08T09:00:00+09:00',
                       published_at='2026-11-08T09:00:00+09:00',
                       published_url=f'https://onnellab.com/blog/{row["primary_language"].lower()}/{preview.SLUG}/')
        self.assertEqual(selector.duplicates_state(rows), 'published')

    def test_missing_source_pins_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'manifest.json').write_text(json.dumps(dict(schema=1,slug=preview.SLUG,
                state='draft_not_ready',queue_modified=False,new_topic_ids_allocated=False,
                scheduled_at=None,published_at=None)))
            with patch.object(preview, 'REVIEWED_BLOBS', {}), self.assertRaisesRegex(ValueError, 'pins incomplete'):
                preview.validate_drafts(root)

    def test_existing_verification_ref_is_not_hijacked(self):
        for ref,name in selector.REFS.items():
            result=selector.selection_environment([self.idea()],ref=ref,event='push',duplicates_available=True)
            self.assertEqual(result,'PREVIEW_REQUIRED=true\nPREVIEW_RESULT=selected\n'+selector.environment_lines(name))

    def test_isolated_helpers_reject_inside_source_and_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source'; source.mkdir()
            (source/'CODEX.md').write_text('fixture')
            inventory={'CODEX.md':preview.digest(b'fixture')}
            with self.assertRaises(ValueError): preview.copy_source(source,source/'stage',inventory)
            preview.copy_source(source,root/'stage',inventory)
            self.assertEqual((source/'CODEX.md').read_bytes(),b'fixture')
            self.assertEqual((root/'stage/CODEX.md').read_bytes(),b'fixture')
            with self.assertRaises(ValueError): preview.safe_native_path(root,'../outside')


class StagingAndRegistration(unittest.TestCase):
    def stage_fixture(self, root):
        from topic_management import TOPIC_HEADER
        with (ROOT/'data/topics.csv').open(newline='') as stream:
            live=list(csv.DictReader(stream))
        seed_slug='compare-playlist-reference-paths-before-moving-files'
        unrelated=[r for r in live if r['slug'] not in (preview.SLUG,seed_slug)]
        # Explicit historical idea fixture, not today's mutable publication state.
        original=next(dict(r) for r in live if r['id']=='TOPIC-0087')
        original.update(status='idea',canonical_path='',scheduled_at='',published_at='',published_url='',updated_at='')
        for rel in ('data/topics.csv','topics/topics.csv'):
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=TOPIC_HEADER);writer.writeheader();writer.writerows(unrelated+[original])
        (root/'data/apps_registry.csv').write_bytes((ROOT/'data/apps_registry.csv').read_bytes())
        p=root/'preview/music-duplicates/idea_seeds.json';p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes((ROOT/'preview/music-duplicates/idea_seeds.json').read_bytes())
        drafts={locale:dict(question='Which copy?',title='Compare files',primary_keyword='music files',secondary_keywords='') for locale in preview.LOCALES}
        return unrelated,drafts

    def test_only_nine_candidate_rows_and_one_seed_change_in_disposable_stage(self):
        before=(ROOT/'data/topics.csv').read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);unrelated,drafts=self.stage_fixture(root)
            store,candidates,seeds=preview.stage_topics(root,drafts)
            self.assertEqual(len(candidates),9);self.assertEqual(len(seeds),1)
            self.assertEqual({r['primary_language'] for r in candidates},set(preview.LOCALES))
            self.assertTrue(all(r['status']=='draft' and not any(r[k] for k in ('scheduled_at','published_at','published_url')) for r in candidates))
            ids={r['id'] for r in unrelated}
            self.assertEqual([r for r in store.read() if r['id'] in ids],unrelated)
            self.assertEqual((root/'data/topics.csv').read_bytes(),(root/'topics/topics.csv').read_bytes())
        self.assertEqual((ROOT/'data/topics.csv').read_bytes(),before)

    def test_duplicate_and_review_candidate_are_rejected_without_mutation(self):
        for mode in ('duplicate','review'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);_,drafts=self.stage_fixture(root)
                for rel in ('data/topics.csv','topics/topics.csv'):
                    p=root/rel
                    with p.open(newline='') as stream:
                        reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
                    row=next(r for r in rows if r['id']=='TOPIC-0087')
                    if mode=='duplicate': rows.append(dict(row,id='TOPIC-9999'))
                    else: row['status']='review'
                    with p.open('w',newline='') as stream:
                        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
                before={rel:(root/rel).read_bytes() for rel in ('data/topics.csv','topics/topics.csv')}
                with self.assertRaisesRegex(ValueError,'no longer an idea'): preview.stage_topics(root,drafts)
                self.assertEqual(before,{rel:(root/rel).read_bytes() for rel in before})

    def registered_fixture(self, root):
        from topic_management import TOPIC_HEADER
        rows=[]
        for locale,topic_id in preview.REGISTERED_IDS.items():
            row=dict.fromkeys(TOPIC_HEADER,'')
            row.update(id=topic_id,primary_language=locale,category='music',slug=preview.SLUG,
                       status='review',review_required='true',canonical_path=f'generated/markdown/{locale}/music/{preview.SLUG}.md')
            rows.append(row)
        for rel in ('data/topics.csv','topics/topics.csv'):
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=TOPIC_HEADER);writer.writeheader();writer.writerows(rows)
        entries=[]
        for rel in preview.native_output_paths():
            p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
            raw=b'isolated fixture'
            if rel.endswith('/review.json'):
                locale=rel.split('/')[2];raw=json.dumps(dict(version=4,topic_id=preview.REGISTERED_IDS[locale])).encode()
            p.write_bytes(raw);entries.append(preview.native_entry(rel,raw))
        audit=dict(schema=1,kind='review_supply_audit_not_publication_receipt',slug=preview.SLUG,category='music',stage='review',
                   scheduled_at=None,published_at=None,published_url=None,queue_ids=list(preview.REGISTERED_IDS.values()),reviewed_files=entries,
                   reviewed_source_git_blobs=preview.REVIEWED_BLOBS,reviewed_svg_git_blobs=preview.REVIEWED_SVG_BLOBS)
        p=root/preview.REGISTERED_AUDIT;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(audit))

    def test_registered_path_calls_native_gate_without_rewriting_any_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.registered_fixture(root)
            before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(preview,'validate_drafts'),patch('check_nine_language_publication.check_reviewed_candidates') as gate:
                candidates,manifest=preview.validate_registered_candidates(root)
            gate.assert_called_once_with(root/'data/topics.csv')
            self.assertEqual(len(candidates),9);self.assertEqual(len(manifest['files']),72)
            self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            p=root/manifest['files'][0]['path'];p.write_bytes(p.read_bytes()+b'changed')
            with patch.object(preview,'validate_drafts'),self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
                preview.validate_registered_candidates(root)


class ReviewedSource(unittest.TestCase):
    def test_final_independently_reviewed_sources_have_all_nine_pins(self):
        import evaluate_article as evaluator
        drafts=preview.validate_drafts(ROOT/preview.DRAFT_DIRECTORY)
        self.assertEqual(set(drafts),set(preview.LOCALES))
        for locale,draft in drafts.items():
            self.assertTrue(draft['question'].endswith(('?','？')))
            self.assertEqual(len(draft['image']['steps']),4)
            self.assertIn(draft['primary_keyword'].lower(),draft['body'].lower())
            self.assertTrue(evaluator.has_required_sections(evaluator.sections(draft['body'])))
            self.assertTrue(evaluator.has_clear_definitions(draft['body'],locale))
            self.assertEqual(len(re.findall(r'^\d+\. ',draft['body'],re.M)),5)
            self.assertEqual(len(re.findall(r'^### ',draft['body'],re.M)),3)
            self.assertEqual(len(re.findall(r'^\|',draft['body'],re.M)),5)

    def test_every_source_pin_rejects_mutation(self):
        source=ROOT/preview.DRAFT_DIRECTORY
        for locale in preview.LOCALES:
            for relative in (locale+'.md','assets/'+locale+'/workflow-diagram.svg'):
                with self.subTest(path=relative), tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp)/'draft';shutil.copytree(source,root)
                    path=root/relative;path.write_bytes(path.read_bytes()+b'\n')
                    with self.assertRaisesRegex(ValueError,'fingerprint mismatch'):
                        preview.validate_drafts(root)

if __name__ == '__main__': unittest.main()
