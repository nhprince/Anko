"""Turns calculation results into natural-display trees (mathtree.Seq)."""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from . import numeric as num
from .interp import DMSVal, PairVal, Settings
from .mathtree import (Seq, Node, tok, seq_from, structure, frac_node, sqrt_node, sup_node, matrix_node)
from .values import (CNum, Exact, Matrix, Vec, fl, is_zero, r_neg, r_cmp, c_abs, cparts, sign, ZERO)

MINUS = "−"


# ---------------------------------------------------------------------------
# decimal text
# ---------------------------------------------------------------------------
def _decimal_of(x) -> Decimal:
    if isinstance(x, Fraction):
        with localcontext() as c:
            c.prec = 60
            return Decimal(x.numerator) / Decimal(x.denominator)
    return Decimal(repr(float(x)))


def _sig_parts(d: Decimal, digits: int):
    """(digit-string with `digits` digits, exponent10) for |d|>0"""
    d = abs(d)
    e = d.adjusted()
    with localcontext() as c:
        c.prec = 80
        q = d.scaleb(-e).quantize(Decimal(1).scaleb(-(digits - 1)), rounding=ROUND_HALF_UP)
    if q >= 10:
        q = (q / 10).quantize(Decimal(1).scaleb(-(digits - 1)), rounding=ROUND_HALF_UP)
        e += 1
    ds = f"{q:f}".replace(".", "")
    ds = ds.ljust(digits, "0")[:digits]
    return ds, e


def _plain(ds: str, e: int) -> str:
    ds = ds.rstrip("0") or "0"
    if e >= 0:
        ip = ds[: e + 1].ljust(e + 1, "0")
        fp = ds[e + 1:]
    else:
        ip = "0"
        fp = "0" * (-e - 1) + ds
    return ip + ("." + fp if fp else "")


def _group(s: str) -> str:
    ip, _, fp = s.partition(".")
    ip = f"{int(ip):,}"
    return ip + ("." + fp if fp else "")


def number_parts(x, s: Settings):
    """returns (negative, mantissa_text, exponent or None)"""
    if isinstance(x, float) and (x != x or math.isinf(x)):
        raise ValueError("nan")
    d = _decimal_of(x)
    if d == 0:
        return False, "0", None
    neg = d < 0
    n = max(1, min(int(s.digits), 15 if s.notation != "fix" else 9))
    mode = s.notation
    if mode == "fix":
        q = abs(d).quantize(Decimal(1).scaleb(-n), rounding=ROUND_HALF_UP)
        if q >= Decimal("1e10"):
            mode = "norm1"
        else:
            t = f"{q:f}"
            if q == 0:
                neg = False
            return neg, t, None
    ds, e = _sig_parts(d, max(n, 1) if mode != "sci" else max(n, 1))
    if mode == "eng":
        ee = (e // 3) * 3
        shift = e - ee
        ip = ds[: shift + 1].ljust(shift + 1, "0")
        fp = ds[shift + 1:].rstrip("0")
        return neg, ip + ("." + fp if fp else ""), ee
    if mode == "sci":
        fp = ds[1:].rstrip("0")
        return neg, ds[0] + ("." + fp if fp else ""), e
    lo = -2 if mode == "norm1" else -9
    if e < lo or e >= 10:
        fp = ds[1:].rstrip("0")
        return neg, ds[0] + ("." + fp if fp else ""), e
    return neg, _plain(ds, e), None


def decimal_seq(x, s: Settings, with_sign=True) -> Seq:
    neg, m, e = number_parts(x, s)
    if s.thousands and e is None:
        m = _group(m)
    out = Seq()
    if neg and with_sign:
        out.add(tok(MINUS))
    out.add(tok(m))
    if e is not None:
        out.add(tok("×10"))
        out.add(sup_node(seq_from((MINUS if e < 0 else "") + str(abs(e)))))
    return out


def decimal_text(x, s: Settings) -> str:
    neg, m, e = number_parts(x, s)
    t = ("-" if neg else "") + m
    if e is not None:
        t += f"E{e}"
    return t


# ---------------------------------------------------------------------------
# exact forms
# ---------------------------------------------------------------------------
def _digits_len(n: int) -> int:
    return len(str(abs(n)))


def _rational_seq(f: Fraction, s: Settings, with_sign=True) -> Seq:
    if f.denominator == 1:
        if abs(f.numerator) >= 10 ** 10:
            return decimal_seq(f, s, with_sign)
        out = Seq()
        if f < 0 and with_sign:
            out.add(tok(MINUS))
        t = str(abs(f.numerator))
        if s.thousands:
            t = f"{int(t):,}"
        out.add(tok(t))
        return out
    n, d = abs(f.numerator), f.denominator
    if _digits_len(n) > 10 or _digits_len(d) > 10:
        return decimal_seq(f, s, with_sign)
    out = Seq()
    if f < 0 and with_sign:
        out.add(tok(MINUS))
    if s.mixed and n > d:
        w, r = divmod(n, d)
        out.add(structure("mixed", seq_from(str(w)), seq_from(str(r)), seq_from(str(d))))
    else:
        out.add(frac_node(seq_from(str(n)), seq_from(str(d))))
    return out


def _term_body(c: int, r: int, k: int, first_in_num: bool) -> Seq:
    """coefficient * pi^k * sqrt(r)  for a positive integer coefficient c"""
    out = Seq()
    show_c = c != 1 or (r == 1 and k == 0)
    if show_c:
        out.add(tok(str(c)))
    if k:
        out.add(tok("π"))
        if k != 1:
            out.add(sup_node(seq_from(str(k))))
    if r != 1:
        out.add(sqrt_node(seq_from(str(r))))
    return out


def _exact_seq(x: Exact, s: Settings, with_sign=True) -> Seq | None:
    items = sorted(x.t.items(), key=lambda kv: (kv[0][1], 0 if kv[0][0] == 1 else 1, -kv[0][0]))
    ks = [k for (r, k), c in items]
    if len(items) > 1 and min(ks) < 0:
        return None
    from math import gcd
    lcd = 1
    for _, c in items:
        lcd = lcd * c.denominator // gcd(lcd, c.denominator)
    coefs = [(r, k, int(c * lcd)) for (r, k), c in items]
    den_pi = 0
    if len(items) == 1 and coefs[0][1] < 0:
        den_pi = -coefs[0][1]
        coefs = [(coefs[0][0], 0, coefs[0][2])]
    if any(abs(c) > 10 ** 9 or r > 10 ** 9 for r, k, c in coefs):
        return None
    # cancel gcd of the coefficients with lcd
    g = lcd
    for _, _, c in coefs:
        g = gcd(g, abs(c))
    if g > 1:
        lcd //= g
        coefs = [(r, k, c // g) for r, k, c in coefs]
    single = len(coefs) == 1
    out = Seq()
    negative_single = single and coefs[0][2] < 0
    if negative_single and with_sign and (lcd != 1 or den_pi):
        out.add(tok(MINUS))
    num_seq = Seq()
    for idx, (r, k, c) in enumerate(coefs):
        ng = c < 0
        body = _term_body(abs(c), r, k, idx == 0)
        if idx == 0:
            if ng and not (single and (lcd != 1 or den_pi)) and with_sign:
                num_seq.add(tok(MINUS))
        else:
            num_seq.add(tok(MINUS if ng else "+"))
        for it in list(body.items):
            num_seq.add(it)
    if lcd == 1 and not den_pi:
        for it in list(num_seq.items):
            out.add(it)
        return out
    den_seq = Seq()
    if lcd != 1:
        den_seq.add(tok(str(lcd)))
    if den_pi:
        den_seq.add(tok("π"))
        if den_pi != 1:
            den_seq.add(sup_node(seq_from(str(den_pi))))
    out.add(frac_node(num_seq, den_seq))
    return out


# ---------------------------------------------------------------------------
# real values
# ---------------------------------------------------------------------------
def real_seq(x, s: Settings, decimal=False, with_sign=True) -> Seq:
    if isinstance(x, float):
        return decimal_seq(x, s, with_sign)
    if decimal or s.style == "decimal":
        return decimal_seq(fl(x), s, with_sign) if isinstance(x, Exact) else (
            decimal_seq(x, s, with_sign) if x.denominator != 1 or abs(x) >= 10 ** 10 else _rational_seq(x, s, with_sign))
    if isinstance(x, Fraction):
        return _rational_seq(x, s, with_sign)
    r = _exact_seq(x, s, with_sign)
    return r if r is not None else decimal_seq(fl(x), s, with_sign)


def _is_neg(x) -> bool:
    return r_cmp(x, ZERO) < 0


def complex_seq(z: CNum, s: Settings, decimal=False) -> Seq:
    if s.complex_fmt == "polar":
        r = c_abs(z)
        re, im = cparts(z)
        th = num.atan2_unit(im, re, s.angle)
        return seq_from(real_seq(r, s, decimal), "∠", real_seq(th, s, decimal))
    out = Seq()
    re, im = cparts(z)
    if not is_zero(re) and not (isinstance(re, float) and re == 0):
        for it in real_seq(re, s, decimal).items:
            out.add(it)
    neg = _is_neg(im)
    aim = r_neg(im) if neg else im
    if len(out.items) or neg:
        out.add(tok(MINUS if neg else "+"))
    one = isinstance(aim, Fraction) and aim == 1
    if not one:
        multi = isinstance(aim, Exact) and len(aim.t) > 1 and not decimal
        if multi:
            out.add(tok("("))
        for it in real_seq(aim, s, decimal).items:
            out.add(it)
        if multi:
            out.add(tok(")"))
    out.add(tok("i"))
    return out


def dms_seq(deg, s: Settings) -> Seq:
    total = fl(deg)
    neg = total < 0
    total = abs(total)
    d = int(total)
    rem = (total - d) * 60
    m = int(rem + 1e-9)
    sec = (rem - m) * 60
    if abs(sec - round(sec)) < 1e-6:
        sec = round(sec)
        if sec == 60:
            sec, m = 0, m + 1
        if m == 60:
            m, d = 0, d + 1
    sec_txt = f"{sec:.4f}".rstrip("0").rstrip(".") if isinstance(sec, float) else str(sec)
    return seq_from(*(([MINUS] if neg else []) + [f"{d}°{m}′{sec_txt}″"]))


def value_seq(v, s: Settings, decimal=False) -> Seq:
    """the main entry point: any value -> Seq"""
    if isinstance(v, bool):
        return seq_from("True" if v else "False")
    if isinstance(v, (Fraction, Exact, float)):
        return real_seq(v, s, decimal)
    if isinstance(v, CNum):
        return complex_seq(v, s, decimal)
    if isinstance(v, Matrix):
        r, c = v.shape
        cells = [value_seq(x, s, decimal) for row in v.rows for x in row]
        return seq_from(matrix_node(r, c, cells))
    if isinstance(v, Vec):
        cells = [value_seq(x, s, decimal) for x in v.v]
        return seq_from(matrix_node(1, len(v.v), cells))
    if isinstance(v, DMSVal):
        return dms_seq(v.deg, s)
    if isinstance(v, PairVal):
        out = Seq()
        for i, (n, x) in enumerate(zip(v.names, v.vals)):
            if i:
                out.add(tok("  "))
            out.add(tok(n + "="))
            for it in real_seq(x, s, decimal).items:
                out.add(it)
        return out
    return seq_from(str(v))


def value_text(v, s: Settings) -> str:
    """plain-text form used for copying"""
    from .mathtree import to_plain
    return to_plain(value_seq(v, s))


def has_alt_form(v, s: Settings) -> bool:
    """True when S<=>D would change what is displayed"""
    if isinstance(v, (Exact,)):
        return True
    if isinstance(v, Fraction):
        return v.denominator != 1
    if isinstance(v, CNum):
        return True
    if isinstance(v, (Matrix, Vec)):
        return True
    return False
