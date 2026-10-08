from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from blog_branding import approved_blog_mark, branded_blog_svg, BlogBrandError, MARKER
from generate_image_assets import workflow_svg
import publishing as publishing


class BlogBrandingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.home = self.root / 'homepage'; self.home.mkdir()
        self.mark = 'M 0 0 L 100 0 L 100 100 Z'
        self.brand = self.home / 'public/brand/mark-charcoal.svg'
        self.brand.parent.mkdir(parents=True)
        self.brand.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1254 1254"><path d="{self.mark}" fill="#282723"/></svg>')
        for name in publishing.FAVICON_ASSET_NAMES:
            (self.home / 'public' / name).write_bytes(('homepage-approved-' + name).encode())

    def tearDown(self):
        self.temp.cleanup()

    def test_approved_mark_is_read_from_homepage_without_a_second_design_source(self):
        self.assertEqual(approved_blog_mark(self.home), self.mark)
        self.brand.unlink()
        self.assertIsNone(approved_blog_mark(self.home))

    def test_dangling_brand_link_cannot_enable_legacy_icons(self):
        before = {name: (self.home / 'public' / name).read_bytes() for name in publishing.FAVICON_ASSET_NAMES}
        self.brand.unlink(); self.brand.symlink_to(self.home / 'missing.svg')
        with patch('publishing.write_site_icons') as writer, self.assertRaises(publishing.PublishingError):
            publishing.export_site_icons_to_homepage(self.home, False, self.root)
        writer.assert_not_called()
        self.assertEqual(before, {name: (self.home / 'public' / name).read_bytes() for name in before})

    def test_existing_encoding_workflow_is_supported_in_both_languages(self):
        from generate_image_assets import encoding_workflow_svg
        for language in ('en', 'ko'):
            original = encoding_workflow_svg('Encoding check', 'encoding', language)
            output = branded_blog_svg(original, 'workflow', self.mark)
            self.assertIn(MARKER, output)
            self.assertIn('<text x="128" y="586"', output)
            self.assertIn('width="42" height="42"', output)
            self.assertEqual(branded_blog_svg(output, 'workflow', self.mark), output)

    def test_bad_footer_does_not_replace_any_existing_asset(self):
        assets = self.root / 'generated/assets/blog/en/fixture'; assets.mkdir(parents=True)
        target = self.home / 'public/blog-assets/en/fixture'; target.mkdir(parents=True)
        (assets / 'good.svg').write_bytes(b'new valid non-workflow asset')
        (assets / 'workflow-diagram.svg').write_bytes(b'<svg></svg>')
        (target / 'good.svg').write_bytes(b'approved first asset')
        (target / 'workflow-diagram.svg').write_bytes(b'approved workflow')
        before = {p: p.read_bytes() for p in target.iterdir()}
        markdown = '![a](/blog-assets/en/fixture/good.svg)\n![b](/blog-assets/en/fixture/workflow-diagram.svg)'
        with self.assertRaises(publishing.PublishingError):
            publishing.export_blog_assets_to_homepage(markdown, self.home, False, self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in target.iterdir()})

    def test_raster_failure_preserves_all_homepage_destinations(self):
        topic = {'id': 'TOPIC-0044', 'primary_language': 'en', 'category': 'music', 'slug': 'owned-brand'}
        markdown = self.root / 'generated/markdown/en/music/owned-brand.md'
        markdown.parent.mkdir(parents=True)
        markdown.write_text('![Workflow](/blog-assets/en/owned-brand/workflow-diagram.svg)\n')
        assets = self.root / 'generated/assets/blog/en/owned-brand'; assets.mkdir(parents=True)
        (assets / 'workflow-diagram.svg').write_text(workflow_svg('Reviewed workflow', 'audio', 'en'))
        article = publishing.Article(topic, markdown, self.root / 'unused.html', 'blog/en/owned-brand/', 'Reviewed workflow', '', 'Description', '/blog-assets/en/owned-brand/social-card.png', '')
        (assets / 'social-card.svg').write_text(publishing.social_card_svg(article))
        png = assets / 'social-card.png'; png.write_bytes(b'legacy raster')
        topics = self.root / 'data/topics.csv'; topics.parent.mkdir(); topics.write_text('fixture')
        target = self.home / 'public/blog-assets/en/owned-brand'; target.mkdir(parents=True)
        for name in ['workflow-diagram.svg', 'social-card.svg', 'social-card.png']:
            (target / name).write_bytes(('approved-' + name).encode())
        destination = publishing.homepage_destination_for(topic, self.home)
        destination.parent.mkdir(parents=True); destination.write_bytes(b'approved article')
        before = {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        with patch('publishing.validate_homepage_repository'), patch('publishing.load_publishable_articles', return_value=[article]), patch('publishing.write_social_card', return_value=png), patch('publishing.rsvg_convert_command', return_value=['rsvg-convert']), patch('publishing.subprocess.run', side_effect=RuntimeError('injected renderer failure')):
            with self.assertRaisesRegex(RuntimeError, 'injected renderer'):
                publishing.export_markdown_to_homepage(topics, self.home)
        self.assertEqual(before, {p: p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_blog_deploy_preserves_homepage_owned_policy_alias_bytes(self):
        site = self.root / 'generated/site'
        paths = []
        for language, suffix in [('en', ''), ('ko', 'ko')]:
            source = site / 'apps/segra/privacy' / suffix / 'index.html'
            destination = self.home / 'public/apps/segra/privacy' / suffix / 'index.html'
            source.parent.mkdir(parents=True); destination.parent.mkdir(parents=True)
            source.write_bytes(b'legacy policy and old favicon')
            destination.write_bytes(b'approved policy and approved favicon')
            document = self.home / 'src/content/privacy-policies' / language / 'segra.json'
            document.parent.mkdir(parents=True); document.write_text('{}')
            paths.append(destination)
        before = {p: p.read_bytes() for p in paths}
        with patch('publishing.load_privacy_policies', return_value=({}, [{'app_slug': 'segra'}])):
            exports = publishing.export_privacy_pages_to_homepage(site, self.root / 'data/topics.csv', self.home, False)
        self.assertEqual([item.action for item in exports], ['unchanged', 'unchanged'])
        self.assertEqual(before, {p: p.read_bytes() for p in paths})
        paths[1].unlink()
        with patch('publishing.load_privacy_policies', return_value=({}, [{'app_slug': 'segra'}])), self.assertRaises(publishing.PublishingError):
            publishing.export_privacy_pages_to_homepage(site, self.root / 'data/topics.csv', self.home, False)
        self.assertEqual(paths[0].read_bytes(), before[paths[0]])
        self.assertFalse(paths[1].exists())

    def test_unknown_geometry_is_rejected(self):
        self.brand.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0"/></svg>')
        with self.assertRaises(BlogBrandError):
            approved_blog_mark(self.home)

    def test_workflow_mark_is_idempotent_and_preserves_reader_text(self):
        source = workflow_svg('A reviewed workflow', 'A useful task', 'de')
        output = branded_blog_svg(source, 'workflow', self.mark)
        self.assertIn(MARKER, output); self.assertIn(self.mark, output)
        self.assertIn('A reviewed workflow', output)
        self.assertEqual(output, branded_blog_svg(output, 'workflow', self.mark))
        with self.assertRaises(BlogBrandError):
            branded_blog_svg(output, 'workflow', 'M1 1 L2 2')

    def test_unrecognized_footer_fails_closed(self):
        with self.assertRaises(BlogBrandError):
            branded_blog_svg('<svg></svg>', 'workflow', self.mark)

    def test_homepage_icons_are_preserved_without_running_legacy_icon_generator(self):
        before = {name: (self.home / 'public' / name).read_bytes() for name in publishing.FAVICON_ASSET_NAMES}
        with patch('publishing.write_site_icons') as writer:
            publishing.export_site_icons_to_homepage(self.home, False, self.root)
        writer.assert_not_called()
        self.assertEqual(before, {name: (self.home / 'public' / name).read_bytes() for name in publishing.FAVICON_ASSET_NAMES})

    def test_missing_owned_icon_blocks_instead_of_falling_back_to_old_brand(self):
        (self.home / 'public/favicon.svg').unlink()
        with self.assertRaises(publishing.PublishingError):
            publishing.export_site_icons_to_homepage(self.home, False, self.root)

    def test_export_brands_copied_assets_and_renders_workflow_preview_without_mutating_source(self):
        topic = {'id': 'TOPIC-0044', 'primary_language': 'en', 'category': 'music', 'slug': 'owned-brand'}
        markdown = self.root / 'generated/markdown/en/music/owned-brand.md'
        markdown.parent.mkdir(parents=True)
        markdown.write_text('![Workflow](/blog-assets/en/owned-brand/workflow-diagram.svg)\n')
        assets = self.root / 'generated/assets/blog/en/owned-brand'; assets.mkdir(parents=True)
        workflow = assets / 'workflow-diagram.svg'; workflow.write_text(workflow_svg('Reviewed workflow', 'audio', 'en'))
        article = publishing.Article(topic, markdown, self.root / 'unused.html', 'blog/en/owned-brand/', 'Reviewed workflow', '', 'Description', '/blog-assets/en/owned-brand/social-card.png', '')
        social = assets / 'social-card.svg'; social.write_text(publishing.social_card_svg(article))
        png = assets / 'social-card.png'; png.write_bytes(b'legacy engine raster')
        originals = {p: p.read_bytes() for p in [workflow, social, png]}
        topics = self.root / 'data/topics.csv'; topics.parent.mkdir(); topics.write_text('fixture')
        commands = []
        previews = []
        def render(command, **kwargs):
            commands.append(command)
            previews.append(Path(command[5]).read_bytes())
            self.assertIn(MARKER, Path(command[5]).read_text())
            Path(command[-1]).write_bytes(b'approved workflow raster')
        with patch('publishing.validate_homepage_repository'), patch('publishing.load_publishable_articles', return_value=[article]), patch('publishing.write_social_card', return_value=png), patch('publishing.rsvg_convert_command', return_value=['rsvg-convert']), patch('publishing.subprocess.run', side_effect=render):
            publishing.export_markdown_to_homepage(topics, self.home)
        target = self.home / 'public/blog-assets/en/owned-brand'
        self.assertIn(self.mark, (target / 'workflow-diagram.svg').read_text())
        self.assertIn(self.mark, (target / 'social-card.svg').read_text())
        self.assertEqual((target / 'social-card.png').read_bytes(), b'approved workflow raster')
        self.assertEqual(commands[0][1:5], ['-w', '1200', '-h', '675'])
        self.assertEqual(previews[0], (target / 'workflow-diagram.svg').read_bytes())
        self.assertFalse(Path(commands[0][5]).exists())
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})


if __name__ == '__main__':
    unittest.main()
