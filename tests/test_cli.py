from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def make_zip(self, root: Path) -> Path:
        artifact = root / "demo.zip"
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr("README.md", "# demo\n")
            archive.writestr("LICENSE", "MIT\n")
        return artifact

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "distpeek", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_json_output_and_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = self.make_zip(root)
            output = root / "report.json"

            result = self.run_cli(
                "inspect",
                str(artifact),
                "--require",
                "README.md",
                "--format",
                "json",
                "--output",
                str(output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["artifact"], str(artifact))

    def test_policy_failure_returns_one_and_prints_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "leaky.zip"
            with zipfile.ZipFile(artifact, "w") as archive:
                archive.writestr(".env", "secret=never-read\n")

            result = self.run_cli("inspect", str(artifact))

            self.assertEqual(result.returncode, 1)
            self.assertIn("DISTPEEK: BLOCK", result.stdout)
            self.assertNotIn("never-read", result.stdout)

    def test_help_has_the_one_line_promise(self) -> None:
        result = self.run_cli("--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("see exactly what ships", result.stdout)


if __name__ == "__main__":
    unittest.main()
