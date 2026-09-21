from __future__ import annotations

import json
import sys
import tempfile
import unittest
from html import escape
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_manual_publications as v

FEED = 'https://onnellab.hashnode.dev/rss.xml'
CANONICAL = 'https://onnellab.com/blog/en/example/'
ARTICLE = 'https://onnellab.hashnode.dev/example'


def entry(url: str = ARTICLE, content: str = '', title: str = 'Example') -> str:
    return (f'<item><title>{escape(title)}</title><link>{escape(url)}</link>'
            f'<description>{escape(content)}</description></item>')


def rss(*items: str) -> str:
    return '<rss version="2.0"><channel>' + ''.join(items) + '</channel></rss>'


def match(text: str, canonical: str = CANONICAL, slug: str = 'example', feed: str = FEED) -> str:
    return v.rss_matching_item_url(text, canonical, slug, feed)


class RssIdentityTest(unittest.TestCase):
    def test_one_character_slug_in_prose_does_not_match(self):
        self.assertEqual(match(rss(entry('https://onnellab.hashnode.dev/another-post', 'A different article.')), 'https://example.com/a', 'a'), '')

    def test_exact_one_character_article_slug_is_valid(self):
        self.assertEqual(match(rss(entry('https://onnellab.hashnode.dev/a')), 'https://example.com/a', 'a'), 'https://onnellab.hashnode.dev/a')

    def test_slug_prefix_suffix_and_mentions_do_not_match(self):
        for leaf in ['example-two', 'not-example', 'example/comments']:
            with self.subTest(leaf=leaf):
                self.assertEqual(match(rss(entry('https://onnellab.hashnode.dev/' + leaf, 'example', 'example'))), '')

    def test_exact_slug_with_query_and_trailing_slash(self):
        url = ARTICLE + '/?utm_source=rss'
        self.assertEqual(match(rss(entry(url))), url)

    def test_exact_canonical_attribution_handles_different_published_slug(self):
        url = 'https://onnellab.hashnode.dev/a-different-published-title'
        content = f'<p>Originally published at <a href="{CANONICAL}">the original article</a></p>'
        self.assertEqual(match(rss(entry(url, content))), url)

    def test_related_canonical_link_is_not_ownership_evidence(self):
        content = f'<p>Further reading: <a href="{CANONICAL}">example</a></p>'
        self.assertEqual(match(rss(entry('https://onnellab.hashnode.dev/different', content))), '')

    def test_related_link_cannot_extend_an_empty_attribution_paragraph(self):
        content = f'<p>Originally published at</p><p>Further reading: <a href="{CANONICAL}">Example</a></p>'
        self.assertEqual(match(rss(entry('https://onnellab.hashnode.dev/different', content))), '')

    def test_canonical_url_boundary_host_path_query_and_case_are_preserved(self):
        for wrong in [CANONICAL + 'suffix', CANONICAL.replace('onnellab.com', 'onnellab.com.attacker.test'),
                      CANONICAL.replace('/en/', '/ko/'), CANONICAL.replace('example', 'Example'),
                      CANONICAL + '?article=other']:
            with self.subTest(wrong=wrong):
                self.assertEqual(match(rss(entry(content='Originally published at ' + wrong))), '')

    def test_known_conflicting_source_overrides_equal_slug(self):
        self.assertEqual(match(rss(entry(content='Originally published at https://other.test/example'))), '')

    def test_tracking_query_and_fragment_do_not_change_canonical_identity(self):
        self.assertEqual(match(rss(entry(content='Originally published at ' + CANONICAL + '?utm_source=rss#intro'))), ARTICLE)

    def test_multiple_claimed_sources_remain_pending(self):
        content = f'<p>Originally published at {CANONICAL}</p><p>Originally published at https://other.test/example</p>'
        self.assertEqual(match(rss(entry(content=content))), '')

    def test_malformed_xml_html_and_empty_response_fail_closed(self):
        for text in ['<rss><item>example ' + CANONICAL, '<html>example ' + CANONICAL + '</html>', '']:
            with self.subTest(text=text):
                self.assertEqual(match(text), '')

    def test_missing_permalink_never_returns_feed_url(self):
        text = rss(f'<item><description>Originally published at {CANONICAL}</description></item>')
        self.assertEqual(match(text), '')

    def test_feed_root_external_host_and_unsafe_links_are_not_articles(self):
        for url in [FEED, 'https://onnellab.hashnode.dev/', 'https://onnellab.hashnode.dev/feed',
                    'https://other.test/example', 'javascript:alert(1)', 'https://user:pass@onnellab.hashnode.dev/example']:
            with self.subTest(url=url):
                self.assertEqual(match(rss(entry(url, 'Originally published at ' + CANONICAL))), '')

    def test_rss_guid_is_only_a_url_when_permalink_is_true(self):
        for attr, expected in [('', ARTICLE), (' isPermaLink="true"', ARTICLE), (' isPermaLink="false"', '')]:
            with self.subTest(attr=attr):
                self.assertEqual(match(rss(f'<item><guid{attr}>{ARTICLE}</guid></item>')), expected)

    def test_namespaced_content_cdata_attribution(self):
        text = (f'<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item>'
                f'<link>{ARTICLE}-new</link><content:encoded><![CDATA['
                f'<p>Originally published at <a href="{CANONICAL}">Source</a></p>'
                ']]></content:encoded></item></channel></rss>')
        self.assertEqual(match(text), ARTICLE + '-new')

    def test_atom_uses_alternate_href_not_self_or_feed_id(self):
        text = (f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>{FEED}</id>'
                f'<link rel="self" href="{FEED}" type="application/atom+xml"/>'
                '<link rel="alternate" href="/example" type="text/html"/>'
                '</entry></feed>')
        self.assertEqual(match(text), ARTICLE)

    def test_atom_default_link_relation_and_explicit_canonical(self):
        text = (f'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                f'<link href="{ARTICLE}-new"/><link rel="canonical" href="{CANONICAL}"/>'
                '</entry></feed>')
        self.assertEqual(match(text), ARTICLE + '-new')

    def test_atom_id_alone_is_not_a_permalink(self):
        text = f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>{ARTICLE}</id><title>example</title></entry></feed>'
        self.assertEqual(match(text), '')

    def test_medium_recognizes_only_full_slug_and_post_id(self):
        feed = 'https://medium.com/feed/@onnellab.app'
        good = 'https://medium.com/@onnellab.app/example-abcdef123456?source=rss-test'
        self.assertEqual(match(rss(entry(good)), feed=feed), good)
        for url in ['https://medium.com/@onnellab.app/example-more-abcdef123456', 'https://medium.com/@someone-else/example-abcdef123456', 'https://medium.com/feed/@onnellab.app']:
            with self.subTest(url=url):
                self.assertEqual(match(rss(entry(url)), feed=feed), '')

    def test_different_matching_articles_are_ambiguous(self):
        content = 'Originally published at ' + CANONICAL
        self.assertEqual(match(rss(entry(ARTICLE, content), entry(ARTICLE + '-another', content))), '')

    def test_duplicate_feed_entry_is_not_a_second_article(self):
        self.assertEqual(match(rss(entry(), entry())), ARTICLE)

    def test_evidence_is_not_borrowed_from_another_entry_or_channel(self):
        text = rss('<item><description>Originally published at ' + CANONICAL + '</description></item>',
                   entry(ARTICLE + '-other'))
        self.assertEqual(match(text), '')
        self.assertEqual(match(f'<rss><channel><description>Originally published at {CANONICAL}</description>{entry(ARTICLE + "-other")}</channel></rss>'), '')

    def test_defaults_resolve_runtime_adapters_without_live_network(self):
        item = {'manual_key':'topic::hashnode::en::markdown', 'platform':'hashnode', 'slug':'example', 'canonical_url':CANONICAL}
        with patch.object(v, 'fetch_text_url', return_value=rss(entry())) as fetch:
            result = v.verify_item(item)
        self.assertEqual(result.posted_url, ARTICLE)
        fetch.assert_called_once()

    def test_saved_automatic_rss_records_use_article_urls(self):
        state = json.loads(v.DEFAULT_STATE.read_text(encoding='utf-8'))
        with patch.dict('os.environ', {}, clear=True):
            for key, record in state.get('done', {}).items():
                if record.get('marked_by') != 'publication_verifier' or record.get('verification_method') not in {'hashnode_rss', 'medium_rss'}:
                    continue
                self.assertTrue(v.is_feed_article_url(record.get('posted_url', ''), v.rss_url_for(record['platform'])), key)

    def test_negative_evidence_does_not_modify_done_state(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            social, syndication, state, report = [root / name for name in ('social.json', 'syndication.json', 'state.json', 'report.json')]
            social.write_text('{"posts": []}')
            syndication.write_text(json.dumps({'drafts':[{'topic_id':'topic', 'platform':'hashnode', 'language':'en', 'slug':'example', 'canonical_url':CANONICAL}]}))
            original = '{"version":1,"done":{"human":{"marked_by":"human"}},"updated_at":"old"}'
            state.write_text(original)
            with patch.object(v, 'fetch_text_url', return_value=rss(entry(ARTICLE + '-other', 'example'))):
                result = v.verify_manual_publications(social, syndication, state, report)
            self.assertEqual(result, [])
            self.assertEqual(state.read_text(), original)
            self.assertEqual(json.loads(report.read_text())['counts']['pending'], 1)


if __name__ == '__main__':
    unittest.main()
