"""Anko – scientific calculator (GUI).

    python main.py            start the calculator
    python main.py --selftest headless smoke test (used when building the .exe)
"""
import sys

from anko.app import run

if __name__ == "__main__":
    sys.exit(run())
