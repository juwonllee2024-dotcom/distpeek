# Verification record

Status: verified locally on 2026-09-02 before the first public release.

The verification target is the `distpeek` MVP. The test suite covers safe ZIP inspection, TAR inspection, required and forbidden rules, size limits, duplicate normalized paths, unsafe paths, renderers, CLI exit codes, JSON output, and an installed-package smoke path.

## Fresh checks

The repository uses the standard `src` layout, so the project is installed first. This is the same explicit install now used by CI:

```text
python -m pip install --no-deps -e .
```

The first bare `unittest discover` run, before that install, reproduced the expected `ModuleNotFoundError` for the uninstalled `src` package. After adding the explicit install step, all commands were run from the repository root and passed:

| Check | Result |
| --- | --- |
| `ruff check src tests` | PASS |
| `ruff format --check src tests` | PASS |
| `mypy src` | PASS — no issues in 4 source files |
| `python -m unittest discover -s tests -v` | PASS — 11 tests |
| `python -m compileall -q src tests examples` | PASS |
| `python -m build` | PASS — wheel and sdist created |
| `pip-audit --local` | PASS — no known vulnerabilities found |
| `git diff --check` | PASS |

## Real input to real result

The built wheel was installed into a clean offline smoke environment and inspected as an artifact:

```text
distpeek 0.1.0
DISTPEEK: PASS
Artifact: distpeek-0.1.0-py3-none-any.whl
Public files: 10
Declared unpacked bytes: 28,463
Artifact bytes: 11,197
SHA-256: 57d5e5b9241a5c818e1d4ebb3c03eab45e397751813b13689e53ca48662dd706
```

The source distribution was also inspected without extraction or execution:

```text
DISTPEEK: PASS
Artifact: distpeek-0.1.0.tar.gz
Public files: 16
Declared unpacked bytes: 48,336
Artifact bytes: 14,853
SHA-256: b7cc82e082cc263c223ff66100212735ab9d4dab7ab964d01d7af6de4c4e33ca
```

The CI workflow repeats the quality checks, builds the package, installs the wheel with `--no-index`, runs the same wheel inspection, audits dependencies, and checks diff hygiene.

## Security review

The completed Codex Security scan `09f1767d-4bb3-4495-be35-698587510df7` reported 0 findings across the four reviewed surfaces: archive metadata, member safety, CLI boundaries, and repository controls. The review confirmed that the MVP only reads archive metadata and the selected artifact for hashing; it does not extract, import, install, execute, or fetch network content.

The protected TAC advisory was unavailable because its connector was not connected (`USER_NOT_LOGGED_IN`). This is a tooling limitation, not a claim that third-party advisories were checked.
