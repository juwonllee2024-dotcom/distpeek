# Product research and decision

Date: 2026-09-02

## Problem observed

Maintainers review a source tree, then publish a filtered archive. The two are not the same object. A missing file can be caused by an ignore rule, a packaging allowlist, a build step, or a release workflow. The failure is visible to the downstream user, not necessarily to the maintainer.

This is not just a theoretical concern: a Stack Overflow question about inspecting an npm package describes published packages missing required files after `.npmignore` patterns matched them. npm’s current documentation separately recommends reviewing package contents and testing before publishing. Sources: [npm publishing guidance](https://docs.npmjs.com/creating-and-publishing-scoped-public-packages/), [the missing-files question](https://stackoverflow.com/questions/42534163/can-i-inspect-the-contents-of-an-npm-package-before-publish).

GitHub’s Trending page describes its list as what the community is most excited about today. The current direction is crowded with AI and workflow tooling, so this product intentionally chooses a small, inspectable artifact with a visible before/after decision instead of another agent wrapper. Source: [GitHub Trending](https://github.com/trending).

## Four independent innovation questions

### 1. `distpeek` — the release artifact lens (selected)

- **Current fact:** npm exposes `npm pack --dry-run`, and npm recommends reviewing contents; npm’s ecosystem also has package-specific tools such as [packtory](https://github.com/enormora/packtory), which checks emitted TypeScript package contents.
- **Innovation hypothesis:** a language- and registry-neutral reader for the already-built archive will catch a useful class of “source is correct, download is wrong” failures with less setup than a full publishing framework.
- **Different by one thing:** it accepts the artifact itself, reads ZIP/TAR metadata without extracting or executing, and emits one review card with optional required/forbidden rules. It is a boundary inspector, not a registry client, bundler, or source-tree scanner.
- **Smallest seven-day experiment:** have ten maintainers run it on their latest `.whl`, `.tgz`, or `.tar.gz`; count real mismatches, suspicious files, and false-positive warnings.
- **First user:** solo maintainers and small teams publishing libraries or CLI tools.
- **Business hypothesis:** keep the local CLI free; a future hosted team history or release gate could be paid, but the MVP does not require an account or cloud.

### 2. `readmeproof` — executable quickstarts (rejected)

- **Current fact:** [docs-drift](https://github.com/georg-nikola/docs-drift) already validates code blocks in Markdown across several languages and provides CI/JSON/HTML output.
- **Innovation hypothesis:** a tiny “run the first five minutes” checker could reduce broken onboarding.
- **Different by one thing:** it would execute documentation examples in isolated processes.
- **Smallest seven-day experiment:** run it against ten popular repositories and measure broken examples.
- **Why not today:** the core idea and safety model are already clearly occupied; copying it would produce a weaker clone than a fresh artifact boundary.

### 3. `worldcase` — one command, several environments (rejected)

- **Current fact:** [tox](https://tox.wiki/en/stable/how-to/usage.html) and [nox](https://nox.thea.codes/en/stable/) already create environment matrices, and timezone/locale drift is a known source of “works on my machine” failures.
- **Innovation hypothesis:** a compact local matrix focused on timezone, locale, and line endings could make invisible runtime differences visible before CI.
- **Different by one thing:** a single command would render a small diff rather than require a full test-environment configuration.
- **Smallest seven-day experiment:** run date/CSV fixtures across four environment profiles and see whether a developer can diagnose a real failure faster.
- **Why not today:** the implementation is easy, but the product risks becoming a generic preflight wrapper around mature tools; the selected artifact boundary is sharper.

### 4. `folderdiff` — explain two trees (rejected)

- **Current fact:** [diffoscope](https://diffoscope.org/) already compares files, archives, directories, and many binary formats; [compare-dir](https://github.com/kojiishi/compare-dir) and GUI tools cover directory comparison.
- **Innovation hypothesis:** a simple “what did backup miss?” receipt could help people verify copied folders.
- **Different by one thing:** the output would group additions, deletions, and content changes into a shareable receipt.
- **Smallest seven-day experiment:** compare backup pairs and measure whether grouping saves review time.
- **Why not today:** generic directory comparison is already a mature category and overlaps existing portfolio work around file provenance and workspace state.

## Scorecard

Scores are 1–5, not predictions.

| Candidate | Pain | Novelty | Build today | Shareability | OSS fit | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `distpeek` | 5 | 4 | 5 | 4 | 5 | **23** |
| `worldcase` | 4 | 3 | 4 | 3 | 4 | 18 |
| `readmeproof` | 4 | 2 | 4 | 3 | 4 | 17 |
| `folderdiff` | 4 | 1 | 5 | 2 | 4 | 16 |

## Why 23/25 is still uncertain

The pain is concrete and the result is visible, but adoption depends on maintainers adding one more release step. The seven-day experiment must prove that the receipt catches real problems rather than merely producing another report. No star count, download count, or revenue is guaranteed.
