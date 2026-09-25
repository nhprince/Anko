"""Base-N calculations (32-bit two's complement, like the calculator)."""
from __future__ import annotations

from fractions import Fraction

from .parser import parse
from .values import MathErr, SyntaxErr

BITS = 32
MASK = (1 << BITS) - 1
MAXV, MINV = (1 << (BITS - 1)) - 1, -(1 << (BITS - 1))
BASES = {"DEC": 10, "HEX": 16, "BIN": 2, "OCT": 8}


def _wrap_check(v: int) -> int:
    if not MINV <= v <= MAXV:
        raise MathErr("Math ERROR (overflow)")
    return v


def _ev(n):
    k = n[0]
    if k == "num":
        v = int(n[1])
        return v - (1 << BITS) if v > MAXV and v <= MASK else v
    if k == "neg":
        return _wrap_check(-_ev(n[1]))
    if k == "bin":
        op, a, b = n[1], _ev(n[2]), _ev(n[3])
        if op == "+":
            return _wrap_check(a + b)
        if op == "-":
            return _wrap_check(a - b)
        if op == "*":
            return _wrap_check(a * b)
        if op == "/":
            if b == 0:
                raise MathErr("Math ERROR (divide by zero)")
            q = abs(a) // abs(b)
            return _wrap_check(q if (a >= 0) == (b >= 0) else -q)
        ua, ub = a & MASK, b & MASK
        r = {"and": ua & ub, "or": ua | ub, "xor": ua ^ ub, "xnor": ~(ua ^ ub) & MASK}[op]
        return r - (1 << BITS) if r > MAXV else r
    if k == "call":
        name, args = n[1], n[2]
        if len(args) != 1:
            raise SyntaxErr("Syntax ERROR")
        a = _ev(args[0])
        if name == "not":
            r = ~(a & MASK) & MASK
            return r - (1 << BITS) if r > MAXV else r
        if name == "neg":
            return _wrap_check(-a)
    raise SyntaxErr("Syntax ERROR")


def evaluate(text: str, base: int) -> int:
    return _ev(parse(text, base=base))


def to_base(v: int, base: int) -> str:
    if base == 10:
        return str(v)
    u = v & MASK
    digs = "0123456789ABCDEF"
    if u == 0:
        return "0"
    out = ""
    while u:
        out = digs[u % base] + out
        u //= base
    return out


def all_bases(v: int) -> dict:
    return {"DEC": to_base(v, 10), "HEX": to_base(v, 16), "BIN": to_base(v, 2), "OCT": to_base(v, 8)}
