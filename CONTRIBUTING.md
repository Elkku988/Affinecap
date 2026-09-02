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
