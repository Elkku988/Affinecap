# Contributing

Changes should preserve the one-screen public model: issue, consume, transfer,
transition, and inspect live lineage. New features need a concrete use case and
adversarial evidence; this project is intentionally not a workflow engine.

Set up a development environment with:

```bash
python -m pip install -e '.[dev]'
```

Before opening a change, run:

```bash
pytest
ruff check .
ruff format --check .
mypy
python examples/minimal.py
python examples/deployment_approval.py
python -m build
twine check dist/*
```

Bug fixes should add a regression test that names the exact semantic claim.
Documentation must distinguish public-API guarantees from cooperative-code
assumptions and out-of-scope same-interpreter attacks.

## Releasing

Release only a commit whose full CI run is green. Create and push an annotated
stable-version tag such as `v0.1.1`; the publish workflow independently repeats
the compatibility, quality, package, and install checks before using PyPI
Trusted Publishing. PyPI artifacts are immutable.

If publication is interrupted, use GitHub's **Re-run failed jobs** action so
the original retained build artifact is reused. Do not re-run every job. The
workflow refuses remote filenames or hashes that conflict with its artifact;
if that artifact has expired or PyPI holds a conflict, prepare a new patch
version rather than trying to replace published files.
