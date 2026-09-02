from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from distpeek.core import DistpeekError, inspect_archive, render_json, render_markdown


class ArchiveFactory:
    def __init__(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def close(self) -> None:
        self.temp_dir.cleanup()

    def zip(self, name: str, entries: dict[str, bytes]) -> Path:
        target = self.root / name
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for member, content in entries.items():
                archive.writestr(member, content)
        return target

    def tar(self, name: str, entries: dict[str, bytes]) -> Path:
        target = self.root / name
        with tarfile.open(target, "w:gz") as archive:
            for member, content in entries.items():
                info = tarfile.TarInfo(member)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
        return target


class InspectArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.factory = ArchiveFactory()

    def tearDown(self) -> None:
        self.factory.close()

    def test_safe_zip_reports_exact_public_surface(self) -> None:
        artifact = self.factory.zip(
            "demo-1.0.0.whl",
            {
                "demo/__init__.py": b"__version__ = '1.0.0'\n",
                "demo-1.0.0.dist-info/METADATA": b"Name: demo\n",
                "README.md": b"# demo\n",
                "LICENSE": b"MIT\n",
            },
        )

        report = inspect_archive(artifact, required=("README.md", "LICENSE"))

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.member_count, 4)
        self.assertEqual(report.total_bytes, 44)
        self.assertEqual(
            report.sha256,
            hashlib.sha256(artifact.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            [member.path for member in report.members],
            [
                "demo/__init__.py",
                "demo-1.0.0.dist-info/METADATA",
                "README.md",
                "LICENSE",
            ],
        )
        self.assertEqual(report.findings, ())

    def test_tar_flags_missing_required_file_and_secret_named_member(self) -> None:
        artifact = self.factory.tar(
            "demo-1.0.0.tar.gz",
            {
                "demo/__init__.py": b"ok\n",
                ".env": b"DO_NOT_READ=1\n",
            },
        )

        report = inspect_archive(artifact, required=("README.md", "LICENSE"))

        self.assertEqual(report.status, "BLOCK")
        codes = {finding.code for finding in report.findings}
        self.assertEqual(codes, {"secret-name", "required-missing"})
        self.assertTrue(
            all("DO_NOT_READ" not in finding.message for finding in report.findings)
        )

    def test_unsafe_zip_path_is_blocked_without_extracting(self) -> None:
        artifact = self.factory.zip(
            "unsafe.zip",
            {
                "../outside.txt": b"never extract me",
                "safe.txt": b"ok",
            },
        )

        report = inspect_archive(artifact)

        self.assertEqual(report.status, "BLOCK")
        self.assertEqual([finding.code for finding in report.findings], ["unsafe-path"])

    def test_duplicate_normalized_paths_are_blocked(self) -> None:
        target = self.factory.root / "duplicate.zip"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("docs/readme.txt", "one")
            archive.writestr("docs\\readme.txt", "two")

        report = inspect_archive(target)

        self.assertEqual(report.status, "BLOCK")
        self.assertEqual(
            [finding.code for finding in report.findings],
            ["duplicate-path"],
        )

    def test_tar_symlink_is_blocked_without_following_target(self) -> None:
        target = self.factory.root / "link.tar.gz"
        with tarfile.open(target, "w:gz") as archive:
            info = tarfile.TarInfo("docs/latest")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../outside"
            archive.addfile(info)

        report = inspect_archive(target)

        self.assertEqual(report.status, "BLOCK")
        self.assertEqual([finding.code for finding in report.findings], ["link-member"])

    def test_archive_member_limit_is_enforced_before_policy_scan(self) -> None:
        artifact = self.factory.zip(
            "many.zip",
            {"one.txt": b"1", "two.txt": b"2"},
        )

        with self.assertRaisesRegex(DistpeekError, "limit is 1"):
            inspect_archive(artifact, max_members=1)

    def test_forbidden_glob_and_size_limit_are_reported(self) -> None:
        artifact = self.factory.zip(
            "policy.zip",
            {
                "docs/notes.txt": b"12345",
                "build/debug.log": b"1234567890",
            },
        )

        report = inspect_archive(
            artifact,
            forbidden=("docs/*",),
            max_file_bytes=5,
        )

        self.assertEqual(report.status, "BLOCK")
        self.assertEqual(
            {finding.code for finding in report.findings},
            {"forbidden-path", "file-too-large"},
        )

    def test_renderers_are_machine_and_human_readable(self) -> None:
        artifact = self.factory.zip("demo.zip", {"README.md": b"# demo\n"})
        report = inspect_archive(artifact)

        document = json.loads(render_json(report))
        markdown = render_markdown(report)

        self.assertEqual(document["status"], "PASS")
        self.assertIn("DISTPEEK: PASS", markdown)
        self.assertIn("README.md", markdown)


if __name__ == "__main__":
    unittest.main()
