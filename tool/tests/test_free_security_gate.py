import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import free_security_gate as gate


class FreeGateScopeTests(unittest.TestCase):
    def test_snapshot_only_reads_reviewable_regular_files(self):
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as out_name:
            root = Path(root_name)
            (root / "lib").mkdir()
            (root / "lib/app.py").write_text("print('safe')\n", encoding="utf-8")
            (root / "auth.json").write_text("opaque-canary", encoding="utf-8")
            (root / "credentials-prod.json").write_text("opaque-canary-2", encoding="utf-8")
            (root / "photo.png").write_bytes(b"\x89PNG\r\n")
            (root / "outside.py").write_text("outside-canary", encoding="utf-8")
            (root / "lib/link.py").symlink_to(root / "outside.py")

            result = gate._snapshot(
                root,
                {"lib/app.py", "auth.json", "credentials-prod.json", "photo.png", "lib/link.py"},
                Path(out_name),
            )

            self.assertEqual(result.files, ["lib/app.py"])
            self.assertEqual(result.skipped, {"binary_or_unreviewable": 1, "opaque": 2, "symlink": 1})
            self.assertEqual(
                result.digest,
                hashlib.sha256(b"lib/app.py\0print('safe')\n").hexdigest(),
            )
            self.assertFalse((Path(out_name) / "auth.json").exists())
            self.assertFalse((Path(out_name) / "credentials-prod.json").exists())
            self.assertFalse((Path(out_name) / "lib/link.py").exists())

    def test_snapshot_rejects_traversal_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as out_name:
            root = Path(root_name)
            self.assertIsNone(gate._snapshot(root, {"../escape.py"}, Path(out_name)))
            self.assertIsNone(gate._snapshot(root, {str(root / "absolute.py")}, Path(out_name)))

    def test_scope_preserves_newline_filename_and_adds_tracked_locks(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
            (root / "pubspec.lock").write_text("packages: {}\n", encoding="utf-8")
            (root / "stable.py").write_text("print('stable')\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "pubspec.lock", "stable.py"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            unusual = "changed\nname.py"
            (root / unusual).write_text("print('changed')\n", encoding="utf-8")

            scope = gate._scope(root, "standard", None)

            self.assertIsNotNone(scope)
            self.assertEqual(scope.names, {unusual, "pubspec.lock"})

    def test_new_free_environment_names_take_precedence(self):
        with patch.dict(
            os.environ,
            {
                "FREE_SECURITY_REPOSITORY": "/free/root",
                "CODEX_SECURITY_REPOSITORY": "/legacy/root",
                "FREE_SECURITY_DIFF_BASE": "free-base",
                "CODEX_SECURITY_DIFF_BASE": "legacy-base",
            },
            clear=True,
        ):
            self.assertEqual(gate._repo(), Path("/free/root"))
            self.assertEqual(gate._base(), "free-base")


class ScannerContractTests(unittest.TestCase):
    def test_semgrep_rejects_malformed_json_and_empty_coverage(self):
        self.assertEqual(gate._parse_semgrep(0, None, {"lib/app.py"})[0], gate.EXIT_UNVERIFIED)
        empty = {"results": [], "errors": [], "paths": {"scanned": []}, "skipped_rules": [], "engine_requested": "OSS"}
        self.assertEqual(gate._parse_semgrep(0, empty, {"lib/app.py"})[0], gate.EXIT_UNVERIFIED)

    def test_semgrep_rejects_status_and_finding_mismatch(self):
        clean = {"results": [], "errors": [], "paths": {"scanned": ["lib/app.py"]}, "skipped_rules": [], "engine_requested": "OSS"}
        self.assertEqual(gate._parse_semgrep(1, clean, {"lib/app.py"})[0], gate.EXIT_UNVERIFIED)

    @unittest.skipUnless(shutil.which("semgrep"), "free scanner unavailable")
    def test_semgrep_treats_leading_dash_target_as_literal_file(self):
        with tempfile.TemporaryDirectory() as root_name:
            snapshot = Path(root_name)
            target = "--config=unexpected.py"
            (snapshot / target).write_text("print('safe')\n", encoding="utf-8")

            run = gate._semgrep(snapshot, [target])

            self.assertEqual(
                (run.status, run.findings, run.covered, run.errors),
                (0, [], 1, []),
            )

    def test_osv_only_counts_vulnerabilities_and_does_not_invent_severity(self):
        clean = {"results": [{"source": {"path": "pubspec.lock"}, "packages": []}]}
        self.assertEqual(gate._parse_osv(0, clean, "pubspec.lock"), (0, []))
        vulnerable = {
            "results": [
                {
                    "packages": [
                        {
                            "package": {"name": "fixture"},
                            "vulnerabilities": [{"id": "OSV-FIXTURE-1"}],
                        }
                    ]
                }
            ]
        }
        status, findings = gate._parse_osv(1, vulnerable, "pubspec.lock")
        self.assertEqual(status, gate.EXIT_BLOCKING)
        self.assertEqual(findings[0]["severity"], "unknown")
        self.assertEqual(findings[0]["rule_id"], "OSV-FIXTURE-1")

    @unittest.skipUnless(shutil.which("osv-scanner"), "free scanner unavailable")
    def test_installed_osv_scanner_rejects_malformed_lockfile(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            reports = root / "reports"
            snapshot = root / "snapshot"
            reports.mkdir()
            snapshot.mkdir()
            (snapshot / "package-lock.json").write_text("not-json", encoding="utf-8")

            run = gate._osv(snapshot, ["package-lock.json"], reports)

            self.assertEqual((run.status, run.findings, run.covered), (gate.EXIT_UNVERIFIED, [], 0))
            self.assertEqual(run.errors, [{"code": "invalid-lockfile", "path": "package-lock.json"}])

    def test_osv_reports_unsupported_lockfile_without_claiming_coverage(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            reports = root / "reports"
            snapshot = root / "snapshot"
            reports.mkdir()
            snapshot.mkdir()
            (snapshot / "Podfile.lock").write_text("PODS: []\n", encoding="utf-8")

            run = gate._osv(snapshot, ["Podfile.lock"], reports)

            self.assertEqual((run.status, run.findings, run.covered), (gate.EXIT_UNVERIFIED, [], 0))
            self.assertEqual(run.errors, [{"code": "unsupported-lockfile", "path": "Podfile.lock"}])

    @unittest.skipUnless(shutil.which("osv-scanner"), "free scanner unavailable")
    def test_osv_reports_empty_dependency_set_without_claiming_coverage(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            reports = root / "reports"
            snapshot = root / "snapshot"
            reports.mkdir()
            snapshot.mkdir()
            (snapshot / "package-lock.json").write_text(
                json.dumps(
                    {
                        "name": "empty-fixture",
                        "lockfileVersion": 3,
                        "requires": True,
                        "packages": {},
                    }
                ),
                encoding="utf-8",
            )

            run = gate._osv(snapshot, ["package-lock.json"], reports)

            self.assertEqual((run.status, run.findings, run.covered), (gate.EXIT_UNVERIFIED, [], 0))
            self.assertEqual(run.errors, [{"code": "empty-dependency-set", "path": "package-lock.json"}])

    @unittest.skipUnless(shutil.which("gitleaks") and shutil.which("semgrep"), "free scanners unavailable")
    def test_installed_free_scanners_detect_canaries_without_generic_proceed_false_positive(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            reports = root / "reports"
            snapshot = root / "snapshot"
            reports.mkdir()
            snapshot.mkdir()
            (snapshot / "test").mkdir()
            canary = "gl" + "pat-" + "12345678901234567890"
            (snapshot / "secret.py").write_text(
                f'TOKEN = "{canary}"\n', encoding="utf-8"
            )
            (snapshot / "test/tls.py").write_text(
                "requests.get(url, verify=False)\n", encoding="utf-8"
            )
            (snapshot / "Safe.java").write_text(
                "class Safe { void retry() { client.proceed(); } }\n", encoding="utf-8"
            )
            (snapshot / "Bad.java").write_text(
                "class Bad { void onReceivedSslError(WebView v, SslErrorHandler handler, SslError e) { handler.proceed(); } }\n",
                encoding="utf-8",
            )
            (snapshot / "Bad.kt").write_text(
                "class Bad { override fun onReceivedSslError(v: WebView, handler: SslErrorHandler, e: SslError) { handler.proceed() } }\n",
                encoding="utf-8",
            )
            (snapshot / "bad.dart").write_text(
                "final client = HttpClient()..badCertificateCallback = (cert, host, port) => true;\n",
                encoding="utf-8",
            )
            (snapshot / "bad.js").write_text(
                "const options = { rejectUnauthorized: false };\n", encoding="utf-8"
            )
            (snapshot / "--config=unexpected.py").write_text(
                "print('literal filename')\n", encoding="utf-8"
            )
            (snapshot / ".gitleaks.toml").write_text("invalid = [", encoding="utf-8")
            scanned_files = [
                "secret.py", "test/tls.py", "Safe.java", "Bad.java", "Bad.kt",
                "bad.dart", "bad.js", "--config=unexpected.py", ".gitleaks.toml",
            ]

            with patch.dict(os.environ, {"GITLEAKS_CONFIG_TOML": "invalid = ["}):
                g_status, g_findings, g_covered = gate._gitleaks(
                    snapshot, scanned_files, reports
                )
            semgrep_run = gate._semgrep(snapshot, scanned_files)

            self.assertEqual((g_status, g_covered), (gate.EXIT_BLOCKING, 9))
            self.assertEqual(g_findings[0]["path"], "secret.py")
            self.assertEqual(
                (semgrep_run.status, semgrep_run.covered),
                (gate.EXIT_BLOCKING, 8),
            )
            self.assertEqual(
                {finding["path"] for finding in semgrep_run.findings},
                {"Bad.java", "Bad.kt", "bad.dart", "bad.js", "test/tls.py"},
            )


class FreeGateCliTests(unittest.TestCase):
    def _repository(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        (root / "pubspec.lock").write_text("packages: {}\n", encoding="utf-8")
        (root / "app.py").write_text("print('base')\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)

    def test_standard_gate_redacts_secret_finding_and_reports_safe_metadata(self):
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as bin_name:
            root = Path(root_name)
            binaries = Path(bin_name)
            self._repository(root)
            canary = "gl" + "pat-" + "this-value-must-never-appear"
            (root / "app.py").write_text(f"TOKEN = '{canary}'\n", encoding="utf-8")
            self._fake_scanners(binaries, leak=True)
            env = os.environ.copy()
            env["PATH"] = f"{binaries}:{env['PATH']}"
            env["FREE_SECURITY_REPOSITORY"] = str(root)

            completed = subprocess.run(
                [sys.executable, str(Path(gate.__file__)), "standard"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                gate.EXIT_BLOCKING,
                completed.stdout + completed.stderr,
            )
            self.assertNotIn(canary, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "blocking")
            self.assertEqual(
                payload["findings"],
                [{"line": 1, "path": "app.py", "rule_id": "fixture-secret", "scanner": "gitleaks", "severity": "high"}],
            )

    def test_standard_gate_fails_closed_on_semgrep_empty_coverage(self):
        with tempfile.TemporaryDirectory() as root_name, tempfile.TemporaryDirectory() as bin_name:
            root = Path(root_name)
            binaries = Path(bin_name)
            self._repository(root)
            (root / "app.py").write_text("print('changed')\n", encoding="utf-8")
            self._fake_scanners(binaries, empty_semgrep=True)
            env = os.environ.copy()
            env["PATH"] = f"{binaries}:{env['PATH']}"
            env["FREE_SECURITY_REPOSITORY"] = str(root)

            completed = subprocess.run(
                [sys.executable, str(Path(gate.__file__)), "standard"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                check=False,
            )

            self.assertEqual(completed.returncode, gate.EXIT_UNVERIFIED)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["status"], "unverified")
            self.assertEqual(
                payload["scanners"]["semgrep"]["errors"],
                [{"code": "coverage-mismatch", "path": "app.py"}],
            )

    def _fake_scanners(self, directory: Path, *, leak: bool = False, empty_semgrep: bool = False) -> None:
        scripts = {
            "gitleaks": f'''#!/usr/bin/env python3
import pathlib, sys
path = pathlib.Path(sys.argv[sys.argv.index("--report-path") + 1])
path.write_text({'"fixture-secret"\t"app.py"\t1\n'!r} if {leak!r} else "", encoding="utf-8")
raise SystemExit(1 if {leak!r} else 0)
''',
            "semgrep": f'''#!/usr/bin/env python3
import json, pathlib
scanned = [] if {empty_semgrep!r} else [str(path.relative_to(pathlib.Path.cwd())) for path in pathlib.Path.cwd().rglob("*.py")]
print(json.dumps({{"results": [], "errors": [], "paths": {{"scanned": scanned}}, "skipped_rules": [], "engine_requested": "OSS"}}))
''',
            "osv-scanner": '''#!/usr/bin/env python3
import json, pathlib, sys
path = pathlib.Path(sys.argv[sys.argv.index("--output-file") + 1])
path.write_text(json.dumps({"results": []}), encoding="utf-8")
''',
        }
        for name, source in scripts.items():
            path = directory / name
            path.write_text(source, encoding="utf-8")
            path.chmod(0o755)


if __name__ == "__main__":
    unittest.main()
