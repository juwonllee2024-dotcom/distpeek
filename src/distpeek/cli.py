"""Command-line interface for distpeek."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .core import DistpeekError, inspect_archive, render_json, render_markdown

VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="distpeek",
        description="see exactly what ships in a release artifact - before users do.",
    )
    parser.add_argument("--version", action="version", version=f"distpeek {VERSION}")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser(
        "inspect", help="inspect a built ZIP, WHL, TAR, or TGZ without extracting it"
    )
    inspect_parser.add_argument("artifact", type=Path)
    inspect_parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )
    inspect_parser.add_argument(
        "--output", type=Path, help="write the report to a file"
    )
    inspect_parser.add_argument(
        "--require",
        action="append",
        default=[],
        metavar="GLOB",
        help="require a member path or glob; repeatable",
    )
    inspect_parser.add_argument(
        "--forbid",
        action="append",
        default=[],
        metavar="GLOB",
        help="block a member path or glob; repeatable",
    )
    inspect_parser.add_argument(
        "--max-file-bytes",
        type=int,
        metavar="N",
        help="block a member whose declared unpacked size exceeds N",
    )
    inspect_parser.add_argument(
        "--max-members",
        type=int,
        default=100_000,
        metavar="N",
        help="refuse archives declaring more than N entries (default: 100000)",
    )
    inspect_parser.add_argument(
        "--max-declared-bytes",
        type=int,
        default=512 * 1024 * 1024,
        metavar="N",
        help="refuse archives declaring more than N unpacked bytes",
    )
    inspect_parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 1 for warnings as well as blocking findings",
    )
    return parser


def _write_or_print(content: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(content)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8", newline="\n")


def main(argv: Sequence[str] | None = None) -> int:
    # Archive names can contain non-ASCII text; never let a Windows console
    # encoding turn a report into a failed inspection.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(errors="backslashreplace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "inspect":
        parser.error(f"unknown command: {args.command}")

    try:
        report = inspect_archive(
            args.artifact,
            required=args.require,
            forbidden=args.forbid,
            max_file_bytes=args.max_file_bytes,
            max_members=args.max_members,
            max_declared_bytes=args.max_declared_bytes,
        )
        content = (
            render_json(report) if args.format == "json" else render_markdown(report)
        )
        _write_or_print(content, args.output)
    except (DistpeekError, OSError, ValueError) as exc:
        print(f"distpeek: error: {exc}", file=sys.stderr)
        return 2

    if report.status == "BLOCK" or (args.strict and report.status == "WARN"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
