from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from publishing import social_template_context, syndication_intro, syndication_body


class ChannelReuseTest(unittest.TestCase):
    def article(self, markdown):
        return SimpleNamespace(
            topic={'id': 'TOPIC-0099', 'primary_question': 'How can I inspect a file?', 'primary_language': 'en', 'published_url': ''},
            title='Inspect a file', description='Inspect a copy before editing.',
            url_path='/blog/en/inspect/', markdown_path=SimpleNamespace(read_text=Mock(return_value=markdown)),
        )

    def test_optional_evidence_sections_are_reused_for_each_channel(self):
        for headings in [('Demo Steps', 'Workplace Use', 'Process Notes'), ('데모 단계', '업무 활용', '과정 기록'), ('데모 단계', '업무 활용', '과정 설명')]:
            with self.subTest(headings=headings):
                article = self.article(f'## {headings[0]}\n1. Open a sample file.\n2. Search for a word.\n\n## {headings[1]}\nInspect an exported log before handing it to a colleague.\n\n## {headings[2]}\nKeep the original, inspect a copy, then compare the output.\n')
                for platform in ('x', 'bluesky'):
                    context = social_template_context(article, 'https://example.com', platform)
                    self.assertEqual(context['x_summary'], 'Open a sample file.')
                    self.assertEqual(context['bsky_summary'], 'Open a sample file.')
                self.assertEqual(social_template_context(article, 'https://example.com', 'linkedin')['lead'], 'Inspect an exported log before handing it to a colleague.')
                self.assertEqual(syndication_intro(article, 'medium'), 'Keep the original, inspect a copy, then compare the output.')
                self.assertEqual(syndication_intro(article, 'devto'), '')

    def test_absent_optional_evidence_keeps_existing_copy_without_claims(self):
        article = self.article('## Short Answer\nInspect the original without changing it.\n\n## Recommended Workflow\n1. Open a copy.\n')
        self.assertEqual(social_template_context(article, 'https://example.com', 'x')['x_summary'], article.description)
        self.assertEqual(social_template_context(article, 'https://example.com', 'linkedin')['lead'], 'Inspect the original without changing it.')
        self.assertEqual(syndication_intro(article, 'medium'), '')
        self.assertEqual(syndication_body(article, 'Original body and URL.', 'medium'), 'Original body and URL.')


if __name__ == '__main__':
    unittest.main()
