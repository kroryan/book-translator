# Contributing

Thanks for contributing to Book Translator.

## Before You Start

- Read the [README](README.md) and make sure the project runs locally.
- Use Python 3.10 or newer.
- Make sure [Ollama](https://ollama.com/) is installed if your change depends on live model execution.

## Local Setup

```bash
git clone https://github.com/KazKozDev/book-translator.git
cd book-translator
pip install -r requirements.txt
pytest -q
python run.py
```

## Branches and Commits

- Create a branch from `main`.
- Keep changes focused. Small PRs are easier to review and safer to merge.
- Use clear commit messages, for example:
  - `fix: restore docker build for modular layout`
  - `feat: add custom translation instructions`
  - `docs: clarify startup steps`

## Pull Requests

Before opening a PR:

- run `pytest -q`
- update docs if behavior changed
- include screenshots for UI changes when useful

PRs should explain:

- what changed
- why it changed
- how it was verified

## Code Style

- Follow the existing project structure and naming.
- Keep fixes pragmatic and local when possible.
- Do not mix unrelated refactors into a functional fix.
- Preserve user changes and avoid destructive git operations.

## Reporting Bugs

When reporting a bug, include:

- operating system
- Python version
- whether Ollama is running
- target model name
- exact steps to reproduce
- logs or screenshots if relevant

## Feature Requests

Feature requests are welcome, but they should describe:

- the user problem
- the desired behavior
- any constraints or tradeoffs

## Questions

Use GitHub issues for bugs and feature requests. For security issues, follow [SECURITY.md](SECURITY.md).
