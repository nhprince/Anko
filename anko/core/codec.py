"""JSON encoding of calculator values (for saving sessions)."""
from __future__ import annotations

from fractions import Fraction

from .values import CNum, Exact, Matrix, Vec


def encode(v):
    if isinstance(v, bool):
        return {"t": "b", "v": v}
    if isinstance(v, Fraction):
        return {"t": "q", "n": str(v.numerator), "d": str(v.denominator)}
    if isinstance(v, float):
        return {"t": "f", "v": repr(v)}
    if isinstance(v, Exact):
        return {"t": "x", "v": [[r, k, str(c.numerator), str(c.denominator)] for (r, k), c in v.t.items()]}
    if isinstance(v, CNum):
        return {"t": "c", "re": encode(v.re), "im": encode(v.im)}
    if isinstance(v, Matrix):
        return {"t": "m", "v": [[encode(x) for x in r] for r in v.rows]}
    if isinstance(v, Vec):
        return {"t": "v", "v": [encode(x) for x in v.v]}
    return None


def decode(o):
    if o is None:
        return None
    t = o["t"]
    if t == "b":
        return o["v"]
    if t == "q":
        return Fraction(int(o["n"]), int(o["d"]))
    if t == "f":
        return float(o["v"])
    if t == "x":
        return Exact({(r, k): Fraction(int(n), int(d)) for r, k, n, d in o["v"]})
    if t == "c":
        return CNum(decode(o["re"]), decode(o["im"]))
    if t == "m":
        return Matrix([[decode(x) for x in r] for r in o["v"]])
    if t == "v":
        return Vec([decode(x) for x in o["v"]])
    return None
