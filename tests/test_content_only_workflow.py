from pathlib import Path
import unittest

import yaml


class ContentOnlyWorkflowTest(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / ".github/workflows/publishing.yml"
        self.workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        self.job = self.workflow["jobs"]["publishing"]
        self.steps = {step.get("name"): step for step in self.job["steps"]}

    def test_content_only_is_explicit_dispatch_opt_in(self):
        option = self.workflow["on"]["workflow_dispatch"]["inputs"]["content_only"]
        self.assertEqual(option["type"], "boolean")
        self.assertEqual(option["default"], "false")
        self.assertEqual(self.job["env"]["CONTENT_ONLY"], "${{ github.event_name == 'workflow_dispatch' && inputs.content_only == true && 'true' || 'false' }}")

    def test_all_live_app_mutation_steps_skip_content_only(self):
        for name in ("Check App Store Versions", "Prepare App Release Candidates", "Create GitHub App Releases", "Generate App Release Report", "Sync App Release Attention Issue"):
            with self.subTest(name=name):
                for historical in (False, True):
                    for dry in (False, True):
                        for content in (False, True):
                            self.assertEqual(self.condition(name, historical, dry, content), not historical and not dry and not content)
                            self.assertEqual(self.condition(name + " Dry Run", historical, dry, content), not historical and dry)

    def test_content_publish_and_deploy_remain_live(self):
        for name in ("Generate Markdown", "Publish Due Articles", "Generate Distribution Drafts", "Deploy", "Post Due Core Distribution"):
            with self.subTest(name=name):
                for historical in (False, True):
                    for dry in (False, True):
                        for content in (False, True):
                            self.assertEqual(self.condition(name, historical, dry, content), not historical and not dry)

    def condition(self, name, historical, dry, content):
        expression = self.steps[name]["if"]
        for key, value in (("HISTORICAL_CORRECTIONS_ONLY", historical), ("DRY_RUN", dry), ("CONTENT_ONLY", content)):
            expression = expression.replace("env." + key, repr("true" if value else "false"))
        return eval(expression.replace("&&", " and ").replace("||", " or "), {"__builtins__": {}}, {})

    def test_content_commit_stages_app_files_only_outside_content_only(self):
        script = self.steps["Commit Content Engine Outputs"]["run"]
        app_paths = "data/app_releases.csv data/app_release_config.csv data/store_versions.csv"
        self.assertIn('if [ "$CONTENT_ONLY" != "true" ]; then\n  git add ' + app_paths + '\nfi', script)
        first_add = next(line for line in script.splitlines() if line.startswith("git add "))
        self.assertIn("data/topics.csv", first_add)
        for path in app_paths.split():
            self.assertNotIn(path, first_add)


if __name__ == "__main__":
    unittest.main()
