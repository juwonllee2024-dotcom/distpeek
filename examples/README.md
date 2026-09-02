# Example: inspect a release archive

Create or build an archive with your normal package tool, then run:

```bash
python -m pip install -e .
distpeek inspect path/to/release.whl \
  --require README.md \
  --require LICENSE \
  --format markdown \
  --output release-review.md
```

For a quick synthetic ZIP on Python 3:

```bash
python -m zipfile -c demo.zip README.md LICENSE
distpeek inspect demo.zip --require README.md --require LICENSE
```

The command only reads archive metadata and writes the requested report. It does not extract or execute the archive.
