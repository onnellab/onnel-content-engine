from pathlib import Path
import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validate_topics as cli
import validate_foundation as foundation
from publication_locales import PUBLICATION_LOCALES
from topic_management import validate_rows, TopicError


class TopicCliLocaleContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.topics = self.root / 'topics.csv'; self.apps = self.root / 'apps.csv'
        with self.apps.open('w', newline='') as stream:
            csv.writer(stream).writerow(cli.APP_HEADER)
        self.rows = []
        for i, language in enumerate(PUBLICATION_LOCALES, 1):
            row = dict.fromkeys(cli.TOPIC_HEADER, '')
            row.update(id=f'TOPIC-{i:04d}', status='idea', category='research', primary_question='Which sources support this claim?', working_title='Trace a source', slug='trace-a-source', primary_language=language, priority='normal', search_intent='learn', primary_keyword='source evidence', evergreen='true', source_type='editorial', review_required='true')
            if language in {'ja', 'zh-Hans', 'zh-Hant'}:
                row['primary_question'] = {'ja': 'この主張の出典は何ですか？', 'zh-Hans': '哪些来源支持这一结论？', 'zh-Hant': '哪些來源支持這個結論？'}[language]
            self.rows.append(row)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self):
        with self.topics.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=cli.TOPIC_HEADER); writer.writeheader(); writer.writerows(self.rows)
        with patch.object(cli, 'TOPICS_PATH', self.topics), patch.object(cli, 'APPS_PATH', self.apps), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return cli.main()

    def test_cli_and_topic_store_share_exact_nine_locales_and_question_punctuation(self):
        self.assertEqual(cli.LANGUAGES, set(PUBLICATION_LOCALES))
        self.assertEqual(len(cli.LANGUAGES), 9)
        self.assertEqual(self.run_cli(), 0)
        validate_rows(self.rows, set())

    def test_foundation_uses_nine_topic_locales_but_preserves_app_language_contract(self):
        self.assertEqual(self.run_cli(), 0)
        self.assertEqual(foundation.TOPIC_LANGUAGES, set(PUBLICATION_LOCALES))
        self.assertEqual(foundation.LANGUAGES, {'en', 'ko'})
        self.assertEqual(len(foundation.validate_topic_file(self.topics, {})), 9)
        self.rows[-1]['primary_language'] = 'ru'; self.run_cli()
        with self.assertRaises(ValueError):
            foundation.validate_topic_file(self.topics, {})

    def test_unregistered_locale_remains_rejected(self):
        self.rows[-1]['primary_language'] = 'ru'
        self.assertEqual(self.run_cli(), 1)
        with self.assertRaises(TopicError):
            validate_rows(self.rows, set())

    def test_title_instead_of_question_remains_rejected(self):
        self.rows[-1]['primary_question'] = 'An informative title'
        self.assertEqual(self.run_cli(), 1)
        with self.assertRaises(TopicError):
            validate_rows(self.rows, set())

    def test_duplicate_locale_slug_and_missing_schedule_remain_rejected(self):
        self.rows[-1]['primary_language'] = self.rows[0]['primary_language']
        self.assertEqual(self.run_cli(), 1)
        self.rows[-1]['primary_language'] = PUBLICATION_LOCALES[-1]
        self.rows[-1]['status'] = 'scheduled'
        self.assertEqual(self.run_cli(), 1)


if __name__ == '__main__':
    unittest.main()
