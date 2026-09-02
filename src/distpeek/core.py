"""Safe, archive-first inspection for release artifacts."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import stat
import tarfile
import zipfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class DistpeekError(Exception):
    """Raised when an artifact cannot be inspected safely."""


@dataclass(frozen=True)
class Member:
    """One file-like entry in an archive, without extracting it."""

    path: str
    size: int
    compressed_size: int | None = None
    kind: str = "file"

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "compressed_size": self.compressed_size,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class Finding:
    """A deterministic policy result for one archive member or rule."""

    code: str
    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class Report:
    """The complete, shareable result of one archive inspection."""

    artifact: str
    archive_type: str
    artifact_bytes: int
    sha256: str
    members: tuple[Member, ...]
    findings: tuple[Finding, ...]
    required: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    max_file_bytes: int | None = None

    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def total_bytes(self) -> int:
        return sum(member.size for member in self.members)

    @property
    def status(self) -> str:
        if any(finding.severity == "error" for finding in self.findings):
            return "BLOCK"
        if self.findings:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict[str, object]:
        return {
            "version": "1",
            "status": self.status,
            "artifact": self.artifact,
            "archive_type": self.archive_type,
            "artifact_bytes": self.artifact_bytes,
            "member_count": self.member_count,
            "total_member_bytes": self.total_bytes,
            "sha256": self.sha256,
            "required": list(self.required),
            "forbidden": list(self.forbidden),
            "max_file_bytes": self.max_file_bytes,
            "findings": [finding.to_dict() for finding in self.findings],
            "members": [member.to_dict() for member in self.members],
        }


_SENSITIVE_NAME = re.compile(
    r"(^|[._-])(secret|secrets|password|passwd|token|credential|credentials)([._-]|$)"
)
_EXAMPLE_SUFFIXES = (".example", ".sample", ".template")
_SENSITIVE_EXACT = {".env", ".npmrc", ".pypirc", "id_rsa", "id_ed25519"}


def _normalize_member_name(name: str) -> tuple[str | None, str | None]:
    """Return a portable member name and an unsafe-path reason, if any."""

    original = name
    normalized = name.replace("\\", "/")
    if "\x00" in normalized:
        return None, "contains a NUL byte"
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return None, "is absolute"

    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if ".." in parts:
        return None, "contains a parent traversal"
    if not parts:
        return None, "has no file name"
    portable = "/".join(parts)
    if portable != original.rstrip("/"):
        # Backslashes are normalized for matching, but traversal and absolute
        # paths were already rejected above.
        return portable, None
    return portable, None


def _is_example_name(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(_EXAMPLE_SUFFIXES) or lower.endswith(
        (".env.example", ".env.sample", ".env.template")
    )


def _name_finding(path: str) -> Finding | None:
    basename = PurePosixPath(path).name.lower()
    if basename in _SENSITIVE_EXACT:
        return Finding(
            code="secret-name",
            severity="error",
            path=path,
            message=(
                "filename resembles a credential or local secret; remove it or "
                "review the allowlist"
            ),
        )
    if basename.startswith(".env.") and not _is_example_name(basename):
        return Finding(
            code="secret-name",
            severity="error",
            path=path,
            message=(
                "environment file is likely machine-specific; do not ship it by "
                "accident"
            ),
        )
    if _SENSITIVE_NAME.search(basename) and not _is_example_name(basename):
        return Finding(
            code="secret-name",
            severity="error",
            path=path,
            message=(
                "filename contains a credential-like marker; review before publishing"
            ),
        )
    if basename.endswith((".key", ".p12", ".pfx")):
        return Finding(
            code="secret-name",
            severity="error",
            path=path,
            message=(
                "private-key or certificate-container extension should not ship "
                "by default"
            ),
        )
    if basename.endswith(".pem"):
        return Finding(
            code="certificate-name",
            severity="warning",
            path=path,
            message="PEM files can be public or private; review this release member",
        )
    return None


def _sha256(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
    except OSError as exc:
        raise DistpeekError(f"cannot read artifact {path}: {exc}") from exc
    return size, digest.hexdigest()


def _validate_limits(
    member_count: int,
    declared_bytes: int,
    max_members: int,
    max_declared_bytes: int,
) -> None:
    if member_count > max_members:
        raise DistpeekError(
            f"artifact declares {member_count} members; limit is {max_members}"
        )
    if declared_bytes > max_declared_bytes:
        raise DistpeekError(
            f"artifact declares {declared_bytes} unpacked bytes; "
            f"limit is {max_declared_bytes}"
        )


def _zip_members(
    path: Path,
    max_members: int,
    max_declared_bytes: int,
) -> list[Member]:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            declared_bytes = sum(info.file_size for info in infos)
            _validate_limits(
                len(infos), declared_bytes, max_members, max_declared_bytes
            )
            members: list[Member] = []
            for info in infos:
                normalized, unsafe_reason = _normalize_member_name(info.filename)
                if unsafe_reason:
                    display = info.filename.replace("\n", "\\n")
                    members.append(
                        Member(display, info.file_size, info.compress_size, "unsafe")
                    )
                    continue
                assert normalized is not None
                if info.is_dir():
                    continue
                mode = (info.external_attr >> 16) & 0o170000
                kind = "symlink" if mode == stat.S_IFLNK else "file"
                members.append(
                    Member(normalized, info.file_size, info.compress_size, kind)
                )
            return members
    except (OSError, zipfile.BadZipFile) as exc:
        raise DistpeekError(f"cannot inspect ZIP archive {path}: {exc}") from exc


def _tar_members(
    path: Path,
    max_members: int,
    max_declared_bytes: int,
) -> list[Member]:
    try:
        with tarfile.open(path, mode="r:*") as archive:
            members_info = archive.getmembers()
            declared_bytes = sum(member.size for member in members_info)
            _validate_limits(
                len(members_info), declared_bytes, max_members, max_declared_bytes
            )
            members: list[Member] = []
            for info in members_info:
                normalized, unsafe_reason = _normalize_member_name(info.name)
                if unsafe_reason:
                    display = info.name.replace("\n", "\\n")
                    members.append(Member(display, info.size, None, "unsafe"))
                    continue
                assert normalized is not None
                if info.isdir():
                    continue
                if info.issym() or info.islnk():
                    kind = "symlink" if info.issym() else "hardlink"
                elif info.isfile():
                    kind = "file"
                else:
                    kind = "special"
                members.append(Member(normalized, info.size, None, kind))
            return members
    except (OSError, tarfile.TarError) as exc:
        raise DistpeekError(f"cannot inspect TAR archive {path}: {exc}") from exc


def _archive_members(
    path: Path,
    max_members: int,
    max_declared_bytes: int,
) -> tuple[str, list[Member]]:
    try:
        if zipfile.is_zipfile(path):
            return "zip", _zip_members(path, max_members, max_declared_bytes)
        if tarfile.is_tarfile(path):
            return "tar", _tar_members(path, max_members, max_declared_bytes)
    except OSError as exc:
        raise DistpeekError(f"cannot identify artifact {path}: {exc}") from exc
    raise DistpeekError(
        f"unsupported artifact {path}; expected a ZIP, WHL, TAR, TGZ, "
        "or similar archive"
    )


def _policy_findings(
    members: Sequence[Member],
    required: Sequence[str],
    forbidden: Sequence[str],
    max_file_bytes: int | None,
) -> list[Finding]:
    findings: list[Finding] = []
    paths = {member.path for member in members}
    seen: dict[str, int] = {}
    for member in members:
        seen[member.path] = seen.get(member.path, 0) + 1
        if member.kind == "unsafe":
            findings.append(
                Finding(
                    code="unsafe-path",
                    severity="error",
                    path=member.path,
                    message=(
                        "archive member is absolute or traverses a parent directory"
                    ),
                )
            )
            continue
        name_finding = _name_finding(member.path)
        if name_finding:
            findings.append(name_finding)
        if member.kind in {"symlink", "hardlink", "special"}:
            findings.append(
                Finding(
                    code=(
                        "link-member" if member.kind != "special" else "special-member"
                    ),
                    severity="error",
                    path=member.path,
                    message=(
                        f"archive contains a {member.kind} entry; inspect before "
                        "extraction"
                    ),
                )
            )
        if max_file_bytes is not None and member.size > max_file_bytes:
            findings.append(
                Finding(
                    code="file-too-large",
                    severity="error",
                    path=member.path,
                    message=(
                        f"declared size {member.size} exceeds limit {max_file_bytes}"
                    ),
                )
            )
        for pattern in forbidden:
            if fnmatch.fnmatchcase(member.path, pattern):
                findings.append(
                    Finding(
                        code="forbidden-path",
                        severity="error",
                        path=member.path,
                        message=f"matches forbidden pattern {pattern!r}",
                    )
                )
    for pattern in required:
        if not any(fnmatch.fnmatchcase(path, pattern) for path in paths):
            findings.append(
                Finding(
                    code="required-missing",
                    severity="error",
                    path=pattern,
                    message=f"required member {pattern!r} is absent from the artifact",
                )
            )
    for path, count in seen.items():
        if count > 1:
            findings.append(
                Finding(
                    code="duplicate-path",
                    severity="error",
                    path=path,
                    message=f"archive contains the normalized path {count} times",
                )
            )
    return findings


def inspect_archive(
    artifact: str | Path,
    *,
    required: Iterable[str] = (),
    forbidden: Iterable[str] = (),
    max_file_bytes: int | None = None,
    max_members: int = 100_000,
    max_declared_bytes: int = 512 * 1024 * 1024,
) -> Report:
    """Inspect an archive without extracting or executing anything."""

    path = Path(artifact)
    if not path.exists() or not path.is_file():
        raise DistpeekError(f"artifact does not exist or is not a file: {path}")
    if max_members < 1 or max_declared_bytes < 1:
        raise DistpeekError("archive limits must be positive")
    if max_file_bytes is not None and max_file_bytes < 1:
        raise DistpeekError("--max-file-bytes must be positive")

    required_rules = tuple(required)
    forbidden_rules = tuple(forbidden)
    artifact_bytes, digest = _sha256(path)
    archive_type, members = _archive_members(path, max_members, max_declared_bytes)
    findings = _policy_findings(
        members, required_rules, forbidden_rules, max_file_bytes
    )
    return Report(
        artifact=str(path),
        archive_type=archive_type,
        artifact_bytes=artifact_bytes,
        sha256=digest,
        members=tuple(members),
        findings=tuple(findings),
        required=required_rules,
        forbidden=forbidden_rules,
        max_file_bytes=max_file_bytes,
    )


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: Report) -> str:
    """Render a compact review comment that is safe to paste into a PR."""

    lines = [
        f"# DISTPEEK: {report.status}",
        "",
        "> See exactly what ships - before users do.",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Artifact | `{_markdown_cell(report.artifact)}` |",
        f"| Format | `{report.archive_type}` |",
        f"| Artifact bytes | {report.artifact_bytes:,} |",
        f"| Public files | {report.member_count} |",
        f"| Unpacked bytes | {report.total_bytes:,} |",
        f"| SHA-256 | `{report.sha256}` |",
        "",
    ]
    if report.findings:
        lines.extend(
            [
                "## Review findings",
                "",
                "| Severity | Code | Path | Message |",
                "| --- | --- | --- | --- |",
            ]
        )
        for finding in report.findings:
            lines.append(
                "| "
                + " | ".join(
                    _markdown_cell(value)
                    for value in (
                        finding.severity,
                        f"`{finding.code}`",
                        f"`{finding.path}`",
                        finding.message,
                    )
                )
                + " |"
            )
        lines.append("")
    else:
        lines.extend(["## Review findings", "", "No policy findings.", ""])
    lines.extend(
        [
            "## Public surface",
            "",
            "| Path | Bytes | Compressed | Kind |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for member in report.members:
        compressed = (
            "-" if member.compressed_size is None else f"{member.compressed_size:,}"
        )
        lines.append(
            f"| `{_markdown_cell(member.path)}` | {member.size:,} | "
            f"{compressed} | {member.kind} |"
        )
    lines.extend(
        ["", "Generated locally by `distpeek`; no archive member was extracted.", ""]
    )
    return "\n".join(lines)


def render_json(report: Report) -> str:
    """Render stable JSON for CI and other tools."""

    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n"
