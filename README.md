# Anko — a real scientific calculator, on your desktop

[![CI](https://github.com/nhprince/Anko/actions/workflows/ci.yml/badge.svg)](https://github.com/nhprince/Anko/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/nhprince/Anko)](https://github.com/nhprince/Anko/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A from-scratch GUI scientific calculator in the spirit of the Casio fx-991CW: natural
textbook display (stacked fractions, roots, superscripts), SHIFT/ALPHA keypad, exact
results (fractions, √, π kept symbolic instead of rounded to decimal), and 13 calculation
modes. Built with Python + PySide6 (Qt), packaged to a single `Anko.exe` with PyInstaller.

## Run from source
```
pip install -r requirements.txt
python main.py
```
Headless smoke test (also used before every build): `python main.py --selftest`

## Modes
Calculate · Statistics (1-/2-Var + 7 regressions) · Distribution (Normal/Binomial/Poisson)
· Spreadsheet (A–E × 45, formulas, SUM/MEAN/ranges) · Table (f(x)/g(x)) · Equation
(simultaneous 2–4 unknowns, polynomial degree 2–4) · Inequality (degree 2–4) · Complex
(a+bi / r∠θ) · Base-N (DEC/HEX/BIN/OCT, bitwise ops) · Matrix (A–D, det/inverse/transpose/
RREF) · Vector (A–D, dot/cross/angle/unit) · Ratio · Math Box (dice/coin/random).

Switch modes with the **Apps** button (or `Ctrl+M`); open **Settings** (`Ctrl+,`) for angle
unit, number format (Norm/Fix/Sci/Eng), Math vs Decimal results, complex format, mixed
fractions, digit grouping and theme. `F1` opens in-app help. The side **Panel** shows live
variables (A–F, X, Y, M, Ans) and a searchable function/symbol catalog.

Session (settings, variables, matrices/vectors, and each mode's history/data) is saved
automatically to `%APPDATA%\Anko\session.json` (Windows) or `~/.config/Anko/session.json`
and restored on next launch.

## Engine (`anko/core`, no Qt dependency — independently testable)
- `values.py` — numeric tower: exact rationals, exact `q·√r·πᵏ` sums, complex, matrix, vector
- `parser.py` — tokenizer + recursive-descent parser (implicit multiplication, `nPr`/`nCr`
  infix, DMS, polar `∠`, Base-N grammar)
- `numeric.py` — exact trig for standard angles, adaptive Gauss–Kronrod integration,
  Richardson-extrapolated derivatives, Newton + bracketing root finder
- `interp.py` — the evaluator: ~90 functions, variables/memory, CALC/SOLVE
- `solvers.py` — simultaneous linear systems, polynomial roots (rational-root + closed-form
  quadratic + Durand–Kerner), inequality ranges
- `stats.py` — 1-/2-variable statistics, 7 regression models, Normal/Binomial/Poisson
- `basen.py` — 32-bit two's-complement Base-N arithmetic
- `formatter.py` — value → natural-display tree (fractions, √, mixed numbers, Fix/Sci/Eng)
- `mathtree.py` / `editmodel.py` — the natural-display document model and its cursor,
  templates, undo/redo, used identically by the editable input and read-only results

## UI (`anko/ui`)
- `mathlayout.py` — lays out and paints `mathtree.Seq` (fractions, radicals, Σ/Π/∫, matrices)
- `mathedit.py` — `MathEditor` (editable line), `MathView` (read-only), `TranscriptView`
- `keypad.py` — the SHIFT/ALPHA keypad, key faces drawn with the same layout engine
- `pages.py` / `calcpage.py` — the 13 mode pages
- `dialogs.py` — Apps menu, Settings, Catalog, Constants (CODATA), CALC/SOLVE prompts,
  matrix/vector editor
- `window.py` — main window, LCD chrome, key-action routing, persistence

## Contributing
Bug reports, feature requests, and PRs are welcome — see `CONTRIBUTING.md`. This is a
side project maintained as time allows.

## Tests
```
python tests/test_engine.py      # numeric engine
python tests/test_ui_smoke.py    # fires every keypad action across 5 modes (offscreen)
python tests/test_flows.py       # keypad-driven user flows, settings, theme switch, session
```

## Build the .exe (on Windows)
```
pip install -r requirements.txt pyinstaller
python tools\make_icon.py
pyinstaller anko.spec --noconfirm --clean
```
Produces `dist\Anko\Anko.exe` (a folder build — fast startup). For a single-file exe:
`set ANKO_ONEFILE=1` before running PyInstaller (slower to start, one `Anko.exe`).

## Build the installer (Windows, wizard-based .exe)
Requires [Inno Setup](https://jrsoftware.org/isdl.php) (free) and a folder build from the
step above (`dist\Anko\Anko.exe` must exist — the installer packages that whole folder).
```
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\anko.iss
```
or open `installer\anko.iss` in the Inno Setup Compiler GUI and click **Build**.
Produces `installer\output\AnkoSetup-1.0.0.exe` — a normal Next/Next/Finish installer that
adds Start Menu and (optional) Desktop shortcuts and registers an uninstaller in
*Settings → Apps*. Bump `MyAppVersion` in `installer\anko.iss` for each release.
