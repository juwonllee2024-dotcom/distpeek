# Contributing to distpeek

Thanks for helping make release artifacts easier to review. Keep the project small, deterministic, and dependency-free at runtime.

## Local setup

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

Before opening a pull request, run:

```bash
ruff check src tests
ruff format --check src tests
mypy src
python -m unittest discover -s tests -v
python -m compileall -q src tests examples
python -m build
pip-audit --local
git diff --check
```

## Change rules

- Add a failing test before changing behavior.
- Keep archive inspection non-executing and non-extracting.
- Do not add a runtime dependency without a documented reason.
- Never commit real credentials or private release artifacts.
- Update the README, CHANGELOG, or verification record when user-visible behavior changes.

Small focused pull requests are easiest to review. By submitting a contribution, you agree that it may be distributed under the MIT license.
