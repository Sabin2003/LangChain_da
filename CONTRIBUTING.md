# Contributing to langchain-rabbitmq

Thanks for taking the time to contribute!

## Development setup

```bash
git clone https://github.com/Sabin2003/LangChain_da.git
cd LangChain_da
python -m venv .venv
source .venv/bin/activate
make install
```

## Quality gates

Every PR must pass:

```bash
make lint        # ruff
make typecheck   # pyright --strict
make security    # bandit
make test        # unit tests with >90% coverage
```

Integration / E2E / load tests require Docker:

```bash
make test-integration
make test-e2e
make test-load
```

## Code style

* Strict typing (`from __future__ import annotations`, no implicit `Any`).
* Public APIs **must** have docstrings.
* Pydantic v2 for every external schema.
* No `TODO` comments in merged code — open an issue instead.
* SemVer (`major.minor.patch`) — breaking changes bump the major.

## Pull request checklist

- [ ] Tests added / updated.
- [ ] Coverage stays above 90 %.
- [ ] `CHANGELOG.md` updated under the *Unreleased* section.
- [ ] `mkdocs build --strict` succeeds if documentation changed.

## Releasing

1. Bump `__version__` in `src/langchain_rabbitmq/__init__.py`.
2. Update `CHANGELOG.md` (move *Unreleased* items under a new dated version).
3. Commit and push: `git tag vX.Y.Z && git push --tags`.
4. The `release.yml` workflow publishes to PyPI via OIDC trusted publishing.
