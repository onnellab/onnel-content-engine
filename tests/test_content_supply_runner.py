"""Offline shell-flow regression tests; no Codex, network, or publication calls."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == 'posix' and shutil.which('bash') and shutil.which('flock'),
                     'requires POSIX bash/flock (run under WSL on Windows)')
class ContentSupplyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'installed'
        self.repo.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Runner Test')
        self.git('config', 'user.email', 'runner@example.invalid')
        (self.repo / 'scripts').mkdir()
        shutil.copyfile(ROOT / 'scripts/run_codex_content_supply.sh', self.repo / 'scripts/run_codex_content_supply.sh')
        for folder in ('data', 'topics', 'prompts', 'generated/markdown', 'generated/images',
                       'generated/assets/blog', 'generated/metadata', 'generated/reviews'):
            (self.repo / folder).mkdir(parents=True, exist_ok=True)
            (self.repo / folder / '.gitkeep').touch()
        for name in ('data/topics.csv', 'topics/topics.csv'):
            (self.repo / name).write_text('id,status,slug\nold,published,old-article\n')
        (self.repo / 'generated/markdown/old-article.md').write_text('Published text')
        (self.repo / 'prompts/codex_content_supply.md').write_text('Fixture prompt only')
        self.git('add', '.')
        self.git('commit', '-m', 'Fixture')
        origin = self.root / 'origin.git'
        subprocess.run(['git', 'clone', '--bare', str(self.repo), str(origin)], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(origin))
        (self.repo / 'personal.txt').write_text('Never modify this')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, PATH=f'{self.bin}:{os.environ["PATH"]}',
                        EVENTS=str(self.root / 'events'), CASE='success', ORIGIN_TEST=str(origin),
                        GIT_AUTHOR_NAME='Runner Test', GIT_AUTHOR_EMAIL='runner@example.invalid',
                        GIT_COMMITTER_NAME='Runner Test', GIT_COMMITTER_EMAIL='runner@example.invalid')
        self.command('df', '''echo 'Filesystem 1024-blocks Used Available Capacity Mounted on'
if [[ "$CASE" == low_disk ]]; then free=10; else free=99999999; fi
echo "fixture 999999999 1 $free 1% /"
''')
        self.command('rsvg-convert', 'echo "fixture renderer version"\n')
        self.command('codex', '''echo "codex $*" >> "$EVENTS"
if [[ "$1" == login ]]; then
  if [[ "$CASE" == api_login ]]; then echo 'Logged in using API key'; else echo 'Logged in using ChatGPT'; fi
  exit 0
fi
rsvg-convert --version >> "$EVENTS"
case "$CASE" in
 index_foreign)
   echo 'must not leak' > forbidden.txt; git add forbidden.txt; rm forbidden.txt
   echo 'New draft' > generated/markdown/new-draft.md ;;
 index_published)
   echo 'must not change' > generated/markdown/old-article.md
   git add generated/markdown/old-article.md
   git show HEAD:generated/markdown/old-article.md > generated/markdown/old-article.md
   echo 'New draft' > generated/markdown/new-draft.md ;;
 staged) echo 'New draft' > generated/markdown/new-draft.md; git add generated/markdown/new-draft.md ;;
 concurrent)
   tree=$(git -C "$ORIGIN_TEST" rev-parse main^{tree})
   parent=$(git -C "$ORIGIN_TEST" rev-parse main)
   commit=$(echo 'Concurrent update' | git -C "$ORIGIN_TEST" commit-tree "$tree" -p "$parent")
   git -C "$ORIGIN_TEST" update-ref refs/heads/main "$commit"
   echo 'New draft' > generated/markdown/new-draft.md ;;
 published) echo 'changed' > generated/markdown/old-article.md ;;
 receipt) mkdir -p generated/social; echo changed > generated/social/receipt.json ;;
 row) sed -i 's/old,published/old,review/' data/topics.csv ;;
 symlink) ln -s /tmp generated/markdown/linked ;;
 *) echo 'New draft' > generated/markdown/new-draft.md ;;
esac
''')
        self.command('python3', f'''echo "python3 $*" >> "$EVENTS"
if [[ "$1" == - ]]; then exec '{sys.executable}' "$@"; fi
if [[ "$1" == scripts/check_content_supply.py ]]; then
  if [[ "$CASE" == healthy ]]; then exit 0; fi
  if [[ ! -e "$EVENTS.check" ]]; then touch "$EVENTS.check"; exit 1; fi
  if [[ "$CASE" == shortage ]]; then echo 'insufficient ideas'; exit 1; fi
fi
exit 0
''')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def command(self, name, body):
        path = self.bin / name
        path.write_text('#!/usr/bin/env bash\nset -eu\n' + body)
        path.chmod(0o755)

    def run_case(self, case):
        self.env['CASE'] = case
        before = self.git('status', '--porcelain')
        result = subprocess.run(['bash', str(self.repo / 'scripts/run_codex_content_supply.sh')],
                                env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(before, self.git('status', '--porcelain'))
        self.assertEqual('Never modify this', (self.repo / 'personal.txt').read_text())
        self.assertIn('content supply exit=', result.stdout)
        return result

    def test_dirty_checkout_is_untouched_and_isolated_content_is_pushed(self):
        result = self.run_case('success')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('committed and pushed successfully', result.stdout)
        self.git('fetch', 'origin')
        self.assertEqual('New draft', self.git('show', 'origin/main:generated/markdown/new-draft.md'))
        events = (self.root / 'events').read_text()
        self.assertEqual(2, events.count('--require-healthy --minimum-ideas 8'))

    def test_healthy_queue_uses_no_codex(self):
        self.hide_path_renderer()
        result = self.run_case('healthy')
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertNotIn('codex ', (self.root / 'events').read_text())

    def test_staged_only_content_is_committed_and_pushed(self):
        result = self.run_case('staged')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('committed and pushed successfully', result.stdout)
        self.git('fetch', 'origin')
        self.assertEqual('New draft', self.git('show', 'origin/main:generated/markdown/new-draft.md'))

    def test_lock_contention_is_logged_without_starting_work(self):
        self.command('flock', 'exit 1\n')
        result = self.run_case('success')
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn('another run holds', result.stdout)
        self.assertFalse((self.root / 'events').exists())
        log_path = result.stdout.split('log=', 1)[1].strip()
        self.assertIn('another run holds', Path(log_path).read_text())

    def test_hidden_index_blobs_are_dropped_before_validation_and_commit(self):
        for case in ('index_foreign', 'index_published'):
            with self.subTest(case=case):
                (self.root / 'events.check').unlink(missing_ok=True)
                result = self.run_case(case)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.git('fetch', 'origin')
                self.assertEqual('Published text', self.git('show', 'origin/main:generated/markdown/old-article.md'))
                self.assertEqual('', self.git('ls-tree', '--name-only', 'origin/main', '--', 'forbidden.txt'))
                self.assertEqual('New draft', self.git('show', 'origin/main:generated/markdown/new-draft.md'))

    def test_low_disk_is_logged_before_any_model_use(self):
        result = self.run_case('low_disk')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('requires at least 10 GiB', result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_api_login_is_rejected(self):
        result = self.run_case('api_login')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('ChatGPT subscription login required', result.stdout)
        self.assertNotIn('exec --ephemeral', (self.root / 'events').read_text())

    def hide_path_renderer(self):
        # Make absence deterministic even on CI hosts with librsvg installed.
        (self.bin / 'rsvg-convert').unlink()
        bash_env = self.root / 'bash-env'
        bash_env.write_text('command() { if [[ "$*" == "-v rsvg-convert" ]]; then return 1; fi; builtin command "$@"; }\n')
        self.env['BASH_ENV'] = str(bash_env)

    def test_installed_renderer_is_inherited_without_copying_tools(self):
        self.hide_path_renderer()
        renderer = self.repo / '.tools/librsvg2-bin/usr/bin/rsvg-convert'
        renderer.parent.mkdir(parents=True)
        renderer.write_text('#!/usr/bin/env bash\necho "installed renderer version"\n')
        renderer.chmod(0o755)
        result = self.run_case('success')
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('installed renderer version', result.stdout)
        self.assertIn('exec --ephemeral', (self.root / 'events').read_text())
        self.assertIn('installed renderer version', (self.root / 'events').read_text())
        self.git('fetch', 'origin')
        self.assertEqual('', self.git('ls-tree', '--name-only', 'origin/main', '--', '.tools'))

    def test_missing_renderer_fails_before_login_or_model_use(self):
        self.hide_path_renderer()
        result = self.run_case('success')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('rsvg-convert unavailable', result.stdout)
        self.assertNotIn('codex ', (self.root / 'events').read_text())

    def test_broken_renderer_fails_before_login_or_model_use(self):
        self.command('rsvg-convert', 'exit 1\n')
        result = self.run_case('success')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('rsvg-convert failed its preflight check', result.stdout)
        self.assertNotIn('codex ', (self.root / 'events').read_text())

    def test_insufficient_backlog_cannot_commit(self):
        result = self.run_case('shortage')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('insufficient ideas', result.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('ls-remote', 'origin', 'main').split()[0])

    def test_initial_clone_failure_is_logged(self):
        self.git('remote', 'set-url', 'origin', str(self.root / 'missing.git'))
        result = self.run_case('success')
        self.assertNotEqual(0, result.returncode)
        self.assertIn('does not exist', result.stdout)
        self.assertFalse((self.root / 'events').exists())

    def test_concurrent_remote_update_is_not_rebased_or_overwritten(self):
        result = self.run_case('concurrent')
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn('[rejected]', result.stdout)
        self.git('fetch', 'origin')
        self.assertEqual('Concurrent update', self.git('log', '-1', '--format=%s', 'origin/main'))

    def test_publication_rows_assets_receipts_and_symlinks_are_protected(self):
        for case in ('published', 'row', 'receipt', 'symlink'):
            with self.subTest(case=case):
                (self.root / 'events.check').unlink(missing_ok=True)
                result = self.run_case(case)
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertIn('content supply refused:', result.stdout)
                self.assertEqual(self.git('rev-parse', 'HEAD'), self.git('ls-remote', 'origin', 'main').split()[0])


if __name__ == '__main__':
    unittest.main()
