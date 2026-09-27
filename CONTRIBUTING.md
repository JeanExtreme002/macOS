# Contributing

Bug reports, ideas and pull requests are welcome on
[GitHub](https://github.com/JeanExtreme002/macOS).

## Setup

```bash
git clone https://github.com/JeanExtreme002/macOS.git
cd macOS
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

The `Makefile` wraps every command below: run `make help` to list the targets,
for example `make check` (lint, type check and tests) or `make docs`.

## Tests

```bash
pytest                  # everything, including live tests on your Mac
pytest -m "not live"    # unit tests only (these also run on Linux)
```

The live tests talk to the real system. They restore your clipboard and delete
the Keychain items they create.

## Lint and type check

```bash
flake8 macos tests
mypy macos
```

## Documentation

```bash
pip install -r docs/requirements.txt
python -m sphinx -W -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`.

## Pull requests

- Use [Conventional Commits](https://www.conventionalcommits.org) for the title
  (`feat: ...`, `fix: ...`, `docs: ...`).
- Add a test for every bug fix and new feature.
- Keep the package dependency-free.
