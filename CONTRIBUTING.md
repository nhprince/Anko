# Contributing to Anko

Thanks for considering a contribution — bug reports, feature requests, and pull requests are
all welcome. This project is maintained as time allows, so response times may vary.

## Reporting a bug

Open an [issue](../../issues/new/choose) with:
- What you typed / clicked, and what mode you were in
- What you expected vs. what happened
- Your OS (Anko is built and tested on Windows; other platforms may work via
  `python main.py` but are unsupported)

## Suggesting a feature

Open an issue describing the use case, not just the feature — it's easier to evaluate
"I want to convert between number bases while editing a formula" than "add a button."

## Development setup

```
git clone https://github.com/nhprince/Anko.git
cd Anko
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements.txt
python main.py
```

Run the test suite before opening a PR:
```
python tests/test_engine.py
python tests/test_ui_smoke.py
python tests/test_flows.py
python main.py --selftest
```

## Project layout

- `anko/core/` — the calculation engine. Pure Python, no Qt import anywhere in this
  package — keep it that way, since it's what `test_engine.py` exercises directly.
- `anko/ui/` — PySide6 widgets, layout/painting of the natural display, and the main window.
- `tests/` — see `README.md` for what each test file covers.

## Pull requests

- Keep PRs focused on one change; separate refactors from behaviour changes.
- Add or update a test in `tests/` for engine-level changes (new functions, formatting
  rules, parser behaviour). UI-only changes are harder to unit test — a screenshot in the
  PR description is fine.
- Match the existing style (the codebase avoids abbreviations in public names and keeps
  `anko/core` framework-free).

## Code of conduct

Be respectful and constructive. See `CODE_OF_CONDUCT.md`.
