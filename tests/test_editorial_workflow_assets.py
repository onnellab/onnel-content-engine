from pathlib import Path
import json
import sys
import tempfile
import unittest
from xml.etree import ElementTree
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_image_assets import workflow_svg, generate_image_asset, ImageAssetError
from topic_management import TOPIC_HEADER, write_topics

EDITORIAL = {'subtitle': 'Check your files', 'message': 'Keep originals and recheck the same sample.', 'description': 'Four checks for a local audio library.', 'steps': [['1. Preserve', 'Back up originals'], ['2. Select', 'Choose local files'], ['3. Test', 'Try offline playback'], ['4. Recheck', 'Open the same files']]}


class EditorialWorkflowAssetTest(unittest.TestCase):
    def test_authored_reader_content_is_rendered_instead_of_generic_placeholder(self):
        svg = workflow_svg('A deliberately long title about organizing local audio files without losing originals', 'Local audio', 'en', EDITORIAL)
        headings = [' '.join(group.find('{http://www.w3.org/2000/svg}text').itertext()) for group in ElementTree.fromstring(svg).findall('{http://www.w3.org/2000/svg}g')]
        self.assertEqual(headings, [pair[0] for pair in EDITORIAL['steps']])
        self.assertIn(EDITORIAL['message'], svg)
        self.assertIn(EDITORIAL['description'], svg)
        self.assertNotIn('Generated workflow asset for', svg)

    def test_invalid_authored_structure_and_overflow_are_rejected(self):
        for editorial in [{}, {**EDITORIAL, 'steps': EDITORIAL['steps'][:3]}, {**EDITORIAL, 'steps': [['A heading that is far too long for a single card', 'Detail'], *EDITORIAL['steps'][1:]]}, {**EDITORIAL, 'message': 'Long message ' * 30}]:
            with self.subTest(editorial=editorial), self.assertRaises(ImageAssetError):
                workflow_svg('Title', 'Keyword', 'en', editorial)

    def test_spec_regeneration_preserves_valid_editorial_copy_and_rejects_wrong_identity(self):
        from generate_image_spec import generate_image_spec, ImageSpecError
        from test_image_spec_generation import ImageSpecGenerationTest
        fixture = ImageSpecGenerationTest(); fixture.setUp()
        try:
            markdown = fixture.make_markdown_draft()
            def generate():
                return generate_image_spec(markdown, fixture.topics_path, fixture.apps_path, fixture.image_root, fixture.mirror_path)
            spec_path = generate()
            spec = json.loads(spec_path.read_text())
            spec['editorial_workflow'] = EDITORIAL
            spec_path.write_text(json.dumps(spec))
            rows = fixture.read_topics(); rows[0]['status'] = 'draft'
            write_topics(fixture.topics_path, rows)
            generate()
            self.assertEqual(json.loads(spec_path.read_text())['editorial_workflow'], EDITORIAL)
            rows[0]['status'] = 'draft'; write_topics(fixture.topics_path, rows)
            spec['topic']['id'] = 'TOPIC-9999'; spec_path.write_text(json.dumps(spec))
            before = spec_path.read_bytes()
            with self.assertRaises(ImageSpecError):
                generate()
            self.assertEqual(spec_path.read_bytes(), before)
            self.assertEqual(fixture.read_topics()[0]['status'], 'draft')
        finally:
            fixture.tearDown()

    def test_reviewed_spec_survives_repeated_asset_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); topics = root / 'data/topics.csv'
            row = dict.fromkeys(TOPIC_HEADER, '')
            row.update(id='TOPIC-0044', status='review', category='music', slug='local-audio', primary_language='en', working_title='Local audio', primary_keyword='local audio', canonical_path='generated/markdown/en/music/local-audio.md')
            write_topics(topics, [row])
            markdown = root / row['canonical_path']; markdown.parent.mkdir(parents=True); markdown.write_text('## Recommended Workflow\n\n1. Preserve originals.\n\n## FAQ\n\nQuestions.\n')
            images = root / 'generated/images'; assets = root / 'generated/assets/blog'
            spec = images / 'en/music/local-audio/image_spec.json'; spec.parent.mkdir(parents=True)
            spec.write_text(json.dumps({'workflow_diagrams': [{'title': 'Local audio'}], 'editorial_workflow': EDITORIAL}))
            original = spec.read_bytes()
            with patch('generate_image_assets.rsvg_convert_command', return_value=['renderer']), patch('generate_image_assets.subprocess.run'):
                first = generate_image_asset(spec, topics, images, assets, None)
                svg = first.read_bytes()
                generate_image_asset(spec, topics, images, assets, None)
            self.assertEqual(first.read_bytes(), svg)
            self.assertEqual(spec.read_bytes(), original)
            self.assertEqual(markdown.read_text().count('/blog-assets/en/local-audio/workflow-diagram.svg'), 1)
            self.assertIn(EDITORIAL['message'], first.read_text())


if __name__ == '__main__':
    unittest.main()
