"""Numeric helpers: exact trig for special angles, integration, derivative, root finding."""
from __future__ import annotations

import math
from fractions import Fraction

from .values import (Exact, Fraction as _F, MathErr, PI, ZERO, ONE, mk, r_add, r_div, r_mul, r_neg,
                     r_sub, fl, is_exact)

_r2 = mk({(2, 0): Fraction(1)})
_r3 = mk({(3, 0): Fraction(1)})
_r6 = mk({(6, 0): Fraction(1)})
# sin(d degrees) for d = 0..90 step 15
SIN_TABLE = {
    0: ZERO,
    15: mk({(6, 0): Fraction(1, 4), (2, 0): Fraction(-1, 4)}),
    30: Fraction(1, 2),
    45: mk({(2, 0): Fraction(1, 2)}),
    60: mk({(3, 0): Fraction(1, 2)}),
    75: mk({(6, 0): Fraction(1, 4), (2, 0): Fraction(1, 4)}),
    90: ONE,
}


def _sin_deg_int(d: int):
    d %= 360
    if d <= 90:
        return SIN_TABLE[d]
    if d <= 180:
        return SIN_TABLE[180 - d]
    if d <= 270:
        return r_neg(SIN_TABLE[d - 180])
    return r_neg(SIN_TABLE[360 - d])


def angle_to_degrees_exact(x, unit: str):
    """Exact number of degrees for an exact angle, or None"""
    if isinstance(x, float):
        if x == int(x) and abs(x) < 1e12:
            x = Fraction(int(x))
        else:
            return None
    if unit == "DEG":
        return x if isinstance(x, Fraction) else None
    if unit == "GRA":
        return x * Fraction(9, 10) if isinstance(x, Fraction) else None
    # RAD: need c*pi
    if isinstance(x, Fraction):
        return ZERO if x == 0 else None
    if isinstance(x, Exact) and len(x.t) == 1 and (1, 1) in x.t:
        return x.t[(1, 1)] * 180
    return None


def trig_exact(name: str, x, unit: str):
    """returns exact value or None when no exact form is known"""
    deg = angle_to_degrees_exact(x, unit)
    if deg is None:
        return None
    q = deg / 15
    if q.denominator != 1:
        return None
    d = int(q) * 15
    if name == "sin":
        return _sin_deg_int(d)
    if name == "cos":
        return _sin_deg_int(d + 90)
    if name == "tan":
        c = _sin_deg_int(d + 90)
        if c == 0:
            raise MathErr("Math ERROR")
        return r_div(_sin_deg_int(d), c)
    return None


def to_radians(x: float, unit: str) -> float:
    if unit == "DEG":
        return math.radians(x)
    if unit == "GRA":
        return x * math.pi / 200
    return x


def from_radians(x: float, unit: str) -> float:
    if unit == "DEG":
        return math.degrees(x)
    if unit == "GRA":
        return x * 200 / math.pi
    return x


def trig(name: str, x, unit: str):
    was_float = isinstance(x, float)
    ex = trig_exact(name, x, unit)
    if ex is not None:
        return float(ex) if was_float else ex
    r = to_radians(fl(x), unit)
    if name == "sin":
        return math.sin(r)
    if name == "cos":
        return math.cos(r)
    c = math.cos(r)
    if abs(c) < 1e-14:
        raise MathErr("Math ERROR")
    return math.tan(r)


def deg_to_unit(m: Fraction, unit: str):
    """exact angle: m degrees expressed in `unit`"""
    if unit == "DEG":
        return m
    if unit == "GRA":
        return m * Fraction(10, 9)
    return r_mul(PI, m / 180)


def inv_trig(name: str, x, unit: str):
    v = fl(x)
    if name in ("asin", "acos"):
        if abs(v) > 1 + 1e-15:
            raise MathErr("Math ERROR")
        v = max(-1.0, min(1.0, v))
        rad = math.asin(v) if name == "asin" else math.acos(v)
    else:
        rad = math.atan(v)
    if is_exact(x):
        deg = math.degrees(rad)
        m = round(deg / 15)
        if abs(deg - m * 15) < 1e-9:
            return deg_to_unit(Fraction(m * 15), unit)
    return from_radians(rad, unit)


def atan2_unit(y, x, unit: str):
    yf, xf = fl(y), fl(x)
    if xf == 0 and yf == 0:
        raise MathErr("Math ERROR")
    rad = math.atan2(yf, xf)
    if is_exact(x) and is_exact(y):
        deg = math.degrees(rad)
        m = round(deg / 15)
        if abs(deg - m * 15) < 1e-9:
            return deg_to_unit(Fraction(m * 15), unit)
    return from_radians(rad, unit)


# --------------------------------------------------------------------------
# calculus
# --------------------------------------------------------------------------
_XGK = [0.991455371120812639206854697526329, 0.949107912342758524526189684047851,
        0.864864423359769072789712788640926, 0.741531185599394439863864773280788,
        0.586087235467691130294144838258730, 0.405845151377397166906606412076961,
        0.207784955007898467600689403773245, 0.0]
_WGK = [0.022935322010529224963732008058970, 0.063092092629978553290700663189204,
        0.104790010322250183839876322541518, 0.140653259715525918745189590510238,
        0.169004726639267902826583426598550, 0.190350578064785409913256402421014,
        0.204432940075298892414161999234649, 0.209482141084727828012999174891714]
_WG = [0.129484966168869693270611432679082, 0.279705391489276667901467771423780,
       0.381830050505118944950369775488975, 0.417959183673469387755102040816327]


def _gk15(f, a, b):
    c, h = (a + b) / 2, (b - a) / 2
    fc = f(c)
    resk = fc * _WGK[7]
    resg = fc * _WG[3]
    for j in range(7):
        dx = h * _XGK[j]
        f1, f2 = f(c - dx), f(c + dx)
        resk += _WGK[j] * (f1 + f2)
        if j % 2 == 1:
            resg += _WG[j // 2] * (f1 + f2)
    return resk * h, abs((resk - resg) * h)


def integrate(f, a: float, b: float, tol=1e-12, max_depth=40):
    if a == b:
        return 0.0
    sign = 1.0
    if a > b:
        a, b, sign = b, a, -1.0
    if math.isinf(a) or math.isinf(b):
        raise MathErr("Math ERROR")
    # start with a few sub-intervals so narrow features are less likely to be missed
    n0 = 8
    edges = [a + (b - a) * i / n0 for i in range(n0 + 1)]
    total = 0.0
    stack = [(edges[i], edges[i + 1], 0) for i in range(n0)]
    evals = 0
    while stack:
        lo, hi, d = stack.pop()
        val, err = _gk15(f, lo, hi)
        evals += 15
        if evals > 400000:
            raise MathErr("Time Out")
        if err <= tol * max(1.0, abs(val)) * (hi - lo) / (b - a) or d >= max_depth:
            total += val
        else:
            mid = (lo + hi) / 2
            stack.append((lo, mid, d + 1))
            stack.append((mid, hi, d + 1))
    return sign * total


def derivative(f, a: float):
    """central difference with Richardson extrapolation"""
    h = max(1e-3, abs(a) * 1e-3)
    n = 6
    T = [[0.0] * n for _ in range(n)]
    for i in range(n):
        T[i][0] = (f(a + h) - f(a - h)) / (2 * h)
        for j in range(1, i + 1):
            T[i][j] = T[i][j - 1] + (T[i][j - 1] - T[i - 1][j - 1]) / (4 ** j - 1)
        h /= 2
    return T[n - 1][n - 1]


def _brent(f, a, b, fa, fb):
    for _ in range(200):
        m = (a + b) / 2
        fm = f(m)
        if fm == 0 or abs(b - a) < 1e-15 * max(1.0, abs(m)):
            return m
        if fa * fm < 0:
            b, fb = m, fm
        else:
            a, fa = m, fm
    return (a + b) / 2


def find_root(f, guess: float = 0.0):
    """root of f nearest to `guess` (Newton first, then bracket search)"""

    def safe(x):
        try:
            v = f(x)
            return v if math.isfinite(v) else float("nan")
        except (MathErr, ZeroDivisionError, OverflowError, ValueError):
            return float("nan")

    x = guess
    for _ in range(80):
        fx = safe(x)
        if fx != fx:
            break
        if abs(fx) < 1e-14:
            return x
        h = 1e-6 * max(1.0, abs(x))
        d = (safe(x + h) - safe(x - h)) / (2 * h)
        if d != d or d == 0:
            break
        nx = x - fx / d
        if abs(nx - x) < 1e-14 * max(1.0, abs(x)):
            if abs(safe(nx)) < 1e-9:
                return nx
            break
        x = nx
    best = None
    r = 0.5
    while r < 1e7 and best is None:
        n = 400
        pts = [guess + r * (2 * i / n - 1) for i in range(n + 1)]
        vals = [safe(p) for p in pts]
        cands = []
        for i in range(n):
            a, b, fa, fb = pts[i], pts[i + 1], vals[i], vals[i + 1]
            if fa != fa or fb != fb:
                continue
            if fa == 0:
                cands.append(a)
            elif fa * fb < 0:
                root = _brent(safe, a, b, fa, fb)
                if abs(safe(root)) < 1e-6 * max(1.0, abs(fa), abs(fb)):
                    cands.append(root)
        if cands:
            best = min(cands, key=lambda c: abs(c - guess))
        r *= 4
    if best is None:
        raise MathErr("Can't Solve")
    return best


def tidy(x: float):
    """turn a float that is (nearly) an integer / simple fraction into an exact value"""
    if not math.isfinite(x):
        return x
    r = round(x)
    if abs(x - r) < 1e-10 * max(1.0, abs(x)):
        return Fraction(r)
    fr = Fraction(x).limit_denominator(10000)
    if abs(float(fr) - x) < 1e-12 * max(1.0, abs(x)):
        return fr
    return x
