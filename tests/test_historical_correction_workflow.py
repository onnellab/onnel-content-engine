"""Static branch-contract checks; real site build still runs in canonical CI."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CorrectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / '.github/workflows/publishing.yml').read_text()
        self.steps = {re.match(r'      - name: (.+)\n', block)[1]: block
                      for block in re.split(r'(?=      - name: )', self.text)[1:]}

    def test_all_noncorrection_business_steps_are_gated(self):
        shared = {'Checkout content engine', 'Checkout homepage', 'Configure Node', 'Configure Python',
            'Install system dependencies', 'Install homepage dependencies', 'Wait For Pages Deployment'}
        dedicated = {'Validate Historical Correction Route', 'Deploy Historical Corrections Through Canonical Publisher'}
        for name, block in self.steps.items():
            if name not in shared | dedicated:
                self.assertIn("if: env.HISTORICAL_CORRECTIONS_ONLY != 'true'", block, name)
            if name in dedicated:
                self.assertIn("if: env.HISTORICAL_CORRECTIONS_ONLY == 'true'", block, name)

    def test_existing_single_job_schedule_and_safe_default(self):
        self.assertEqual(re.findall(r'^  ([\w-]+):\n    name:', self.text, re.M), ['publishing'])
        self.assertIn('- cron: "0 0 * * *"', self.text)
        self.assertIn('historical_corrections_only:\n        description:', self.text)
        input_block=self.text.split('      historical_corrections_only:',1)[1].split('      content_only:',1)[0]
        self.assertIn('default: false',input_block)
        self.assertIn("github.event_name == 'workflow_dispatch' && inputs.historical_corrections_only == true", self.text)

    def test_dryrun_and_live_use_same_canonical_entrypoint(self):
        block = self.steps['Deploy Historical Corrections Through Canonical Publisher']
        commands = [l.strip() for l in block.splitlines() if 'python3 scripts/' in l]
        self.assertEqual(len(commands), 2)
        self.assertEqual(commands[0], commands[1] + ' --dry-run')
        self.assertIn('--historical-corrections-only', commands[1])
        self.assertNotRegex(block, r'(generate_|schedule_|post_|privacy|gh workflow)')
        self.assertIn("if: env.DRY_RUN != 'true'", self.steps['Wait For Pages Deployment'])

    def test_actual_conditions_exclude_other_media_for_both_correction_modes(self):
        allowed = {'Checkout content engine', 'Checkout homepage', 'Configure Node', 'Configure Python',
            'Install system dependencies', 'Install homepage dependencies', 'Wait For Pages Deployment',
            'Validate Historical Correction Route', 'Deploy Historical Corrections Through Canonical Publisher'}
        for dry_run in ('true', 'false'):
            active = set()
            for name, block in self.steps.items():
                match = re.search(r'^        if: (.+)$', block, re.M)
                expression = match[1] if match else 'True'
                values = {'env.HISTORICAL_CORRECTIONS_ONLY': 'true', 'env.DRY_RUN': dry_run,
                          'env.CONTENT_ONLY': 'false', 'steps.post_core_distribution.outcome': 'failure'}
                for key, value in values.items(): expression = expression.replace(key, repr(value))
                expression = expression.replace('always()', 'True').replace('&&', ' and ').replace('||', ' or ')
                if eval(expression, {'__builtins__': {}}, {}): active.add(name)
            expected = allowed - ({'Wait For Pages Deployment'} if dry_run == 'true' else set())
            self.assertEqual(active, expected)


if __name__ == '__main__': unittest.main()
