# 📦 distpeek

## See exactly what ships — before users do.

Your source tree is not the product. The archive is.

`distpeek` is a tiny, local-first release lens for `.whl`, `.tar.gz`, `.tgz`, `.zip`, and other ZIP/TAR artifacts. It reads the archive’s public file list **without extracting or executing anything**, then gives you a Markdown review card or CI-ready JSON.

```text
📦 release archive  →  🔍 distpeek  →  ✅ PASS / ⛔ BLOCK  →  📝 shareable receipt
```

No registry upload. No cloud. No code execution. No “I thought that file was included.”

## The 30-second check

```bash
python -m pip install -e .

# Inspect the artifact you are about to publish.
distpeek inspect dist/your_package-1.2.3-py3-none-any.whl \
  --require README.md \
  --require LICENSE

# Produce a machine-readable CI artifact.
distpeek inspect dist/your_package-1.2.3-py3-none-any.whl \
  --format json \
  --output distpeek-report.json
```

For a JavaScript package, run `npm pack --dry-run` or `npm pack` first, then point `distpeek` at the resulting `.tgz`. For any other ecosystem, point it at the built archive your users will download.

## What it catches

- 🔭 **The real public surface** — file paths, declared sizes, compression sizes, archive size, and SHA-256.
- 🚨 **Accidental secrets** — credential-like filenames such as `.env`, `.npmrc`, `id_rsa`, `credentials.json`, `.key`, and `.p12`.
- 🧭 **Unsafe archives** — absolute paths, parent traversal, duplicate normalized paths, symlinks, hardlinks, and special members.
- 📏 **Release policy** — repeatable `--require`, `--forbid`, and `--max-file-bytes` rules.
- 🧾 **Two outputs** — a paste-ready Markdown card for a pull request and stable JSON for CI or another tool.

It deliberately does **not** claim to be a complete secret scanner. It flags high-signal names and never reads member contents. Use a dedicated scanner for content-level detection.

## A release decision in one glance

```text
$ distpeek inspect dist/demo-1.0.0.tar.gz --require README.md --require LICENSE

# DISTPEEK: BLOCK

| Field | Value |
| --- | --- |
| Public files | 4 |
| Unpacked bytes | 61 |
| SHA-256 | 8f… |

| Severity | Code | Path | Message |
| error | secret-name | `.env` | environment file is likely machine-specific; do not ship it by accident |
| error | required-missing | `LICENSE` | required member `LICENSE` is absent from the artifact |
```

Exit codes are automation-friendly:

- `0` — no findings (`PASS` or non-strict `WARN`)
- `1` — a policy finding blocks the artifact (or `--strict` turns a warning into a failure)
- `2` — the artifact or command could not be inspected

## GitHub Actions

```yaml
name: Release surface

on:
  pull_request:
  push:
    tags: ["v*"]

jobs:
  distpeek:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.x"
      - run: python -m pip install build
      - run: python -m build
      - run: python -m pip install .
      - run: >-
          distpeek inspect dist/*.whl
          --format json
          --output distpeek-report.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: distpeek-report
          path: distpeek-report.json
```

## Why this exists

Package managers already know how to create archives. Their output is easy to overlook in a busy release. npm’s own documentation recommends reviewing package contents and testing before publishing, and the long-running npm community question about missing files describes the exact `.npmignore` failure mode. `distpeek` makes the same review a portable, reviewable step for the artifact itself — not the source folder and not a registry account.

## Safety model

- The default path is read-only: `distpeek` never extracts, imports, installs, uploads, or executes archive members.
- Archive member paths are normalized and checked before policy matching.
- ZIP/TAR entry counts and declared unpacked bytes have finite defaults to reduce archive-bomb exposure.
- Findings include paths and metadata, never secret contents.
- The output is a report. A human or CI policy chooses whether to publish.

## Development

```bash
python -m unittest discover -s tests -v
ruff check src tests
ruff format --check src tests
mypy src
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), the [research note](docs/research.md), and the [verification record](docs/verification.md).

## First-user experiment

The first users are maintainers who have ever opened an issue saying “the source has the file, but the published package does not.” The seven-day experiment is simple: ask ten Python/Node/Rust maintainers to run `distpeek` on their latest release archive, record whether it finds one real mismatch or suspicious member, and keep only the checks that produce a useful review decision.

This is a hypothesis, not a star or adoption promise. The open-source wedge is the tiny, dependency-free, ecosystem-neutral receipt that can live beside any release pipeline.

## License

MIT — see [LICENSE](LICENSE).
