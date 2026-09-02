# Security policy

## Scope

`distpeek` is designed to inspect release archives locally without extracting or executing their members. It still handles attacker-controlled archive metadata, so archive parsing bugs and denial-of-service issues are in scope.

`distpeek` is not a complete secret scanner. It checks filenames and archive metadata only; it does not inspect file contents. Do not treat a `PASS` as proof that an archive contains no secret.

## Reporting a vulnerability

Please use GitHub’s private security advisory flow for this repository. If that is unavailable, open an issue with the smallest safe reproduction and avoid posting real credentials or private artifacts.

Please include:

- the affected version or commit;
- the smallest archive or a synthetic archive that reproduces the behavior;
- the command and platform used; and
- the observed impact.

We will acknowledge a report when reviewed and will coordinate a fix and release when the issue is confirmed. Do not run `distpeek` on untrusted archives in a privileged release environment until the archive and policy are reviewed.
