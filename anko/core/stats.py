"""Statistics (1-var, 2-var, regression) and probability distributions."""
from __future__ import annotations

import math
from fractions import Fraction

from .values import (MathErr, Matrix, ZERO, ONE, add, sub, mul, div, fl, r_sqrt, r_cmp, is_real, mat_rref)

REGRESSIONS = ["Linear (a+bx)", "Quadratic (a+bx+cx²)", "Logarithmic (a+b·ln x)", "e^ (a·e^(bx))",
               "ab^ (a·b^x)", "Power (a·x^b)", "Inverse (a+b/x)"]


def _sum(vals):
    s = ZERO
    for v in vals:
        s = add(s, v)
    return s


def _expand(xs, fs):
    out = []
    for x, f in zip(xs, fs):
        n = int(f)
        if n < 0 or n != f:
            raise MathErr("Math ERROR (frequency must be a positive integer)")
        out.extend([x] * n)
        if len(out) > 200000:
            raise MathErr("Math ERROR (too much data)")
    return out


def _median(v):
    n = len(v)
    if n % 2:
        return v[n // 2]
    return div(add(v[n // 2 - 1], v[n // 2]), Fraction(2))


def one_var(xs, fs=None):
    fs = fs or [Fraction(1)] * len(xs)
    if not xs:
        raise MathErr("No data")
    n = _sum(fs)
    sx = _sum(mul(x, f) for x, f in zip(xs, fs))
    sx2 = _sum(mul(mul(x, x), f) for x, f in zip(xs, fs))
    mean = div(sx, n)
    var_pop = sub(div(sx2, n), mul(mean, mean))
    if r_cmp(var_pop, ZERO) < 0:
        var_pop = ZERO
    res = [("n", n), ("x̄", mean), ("Σx", sx), ("Σx²", sx2), ("σx", r_sqrt(var_pop))]
    if r_cmp(n, ONE) > 0:
        var_s = div(mul(var_pop, n), sub(n, ONE))
        res.append(("sx", r_sqrt(var_s)))
    data = sorted(_expand(xs, fs), key=fl)
    m = len(data)
    res.append(("min x", data[0]))
    lower = data[: m // 2]
    upper = data[(m + 1) // 2:]
    res.append(("Q1", _median(lower) if lower else data[0]))
    res.append(("Med", _median(data)))
    res.append(("Q3", _median(upper) if upper else data[-1]))
    res.append(("max x", data[-1]))
    return res


def _lstsq(xs, ys, deg, fs):
    """polynomial least squares with generic arithmetic (exact when data are exact)"""
    n = deg + 1
    pw = [_sum(mul(f, _pow(x, k)) for x, f in zip(xs, fs)) for k in range(2 * deg + 1)]
    rows = []
    for i in range(n):
        row = [pw[i + j] for j in range(n)]
        row.append(_sum(mul(f, mul(y, _pow(x, i))) for x, y, f in zip(xs, ys, fs)))
        rows.append(row)
    red = mat_rref(Matrix(rows), augment_cols=1)
    return [red.rows[i][n] for i in range(n)]


def _pow(x, k):
    r = ONE
    for _ in range(k):
        r = mul(r, x)
    return r


def _corr(xs, ys, fs):
    n = _sum(fs)
    sx = _sum(mul(f, x) for x, f in zip(xs, fs))
    sy = _sum(mul(f, y) for y, f in zip(ys, fs))
    sxx = _sum(mul(f, mul(x, x)) for x, f in zip(xs, fs))
    syy = _sum(mul(f, mul(y, y)) for y, f in zip(ys, fs))
    sxy = _sum(mul(f, mul(x, y)) for x, y, f in zip(xs, ys, fs))
    num_ = sub(mul(n, sxy), mul(sx, sy))
    den = mul(sub(mul(n, sxx), mul(sx, sx)), sub(mul(n, syy), mul(sy, sy)))
    if r_cmp(den, ZERO) <= 0:
        raise MathErr("Math ERROR")
    return div(num_, r_sqrt(den))


def two_var(xs, ys, fs=None, reg=0):
    fs = fs or [Fraction(1)] * len(xs)
    if len(xs) != len(ys) or not xs:
        raise MathErr("Math ERROR")
    n = _sum(fs)
    sx = _sum(mul(f, x) for x, f in zip(xs, fs))
    sy = _sum(mul(f, y) for y, f in zip(ys, fs))
    sx2 = _sum(mul(f, mul(x, x)) for x, f in zip(xs, fs))
    sy2 = _sum(mul(f, mul(y, y)) for y, f in zip(ys, fs))
    sxy = _sum(mul(f, mul(x, y)) for x, y, f in zip(xs, ys, fs))
    mx, my = div(sx, n), div(sy, n)
    vx = max_zero(sub(div(sx2, n), mul(mx, mx)))
    vy = max_zero(sub(div(sy2, n), mul(my, my)))
    res = [("n", n), ("x̄", mx), ("ȳ", my), ("Σx", sx), ("Σy", sy), ("Σx²", sx2), ("Σy²", sy2), ("Σxy", sxy),
           ("σx", r_sqrt(vx)), ("σy", r_sqrt(vy))]
    if r_cmp(n, ONE) > 0:
        res.append(("sx", r_sqrt(div(mul(vx, n), sub(n, ONE)))))
        res.append(("sy", r_sqrt(div(mul(vy, n), sub(n, ONE)))))
    fx = [float(x) if not isinstance(x, float) else x for x in map(fl, xs)]
    fy = list(map(fl, ys))
    ff = list(map(fl, fs))
    predict = None
    if reg == 0:
        b, a = None, None
        coef = _lstsq(xs, ys, 1, fs)
        a, b = coef
        res += [("a", a), ("b", b), ("r", _corr(xs, ys, fs))]
        predict = lambda x, a=a, b=b: fl(a) + fl(b) * x
        inverse = lambda y, a=a, b=b: (y - fl(a)) / fl(b)
    elif reg == 1:
        if len(set(fx)) < 3:
            raise MathErr("Math ERROR")
        a, b, c = _lstsq(xs, ys, 2, fs)
        res += [("a", a), ("b", b), ("c", c)]
        predict = lambda x, a=a, b=b, c=c: fl(a) + fl(b) * x + fl(c) * x * x
        inverse = lambda y, a=a, b=b, c=c: _quad_inv(fl(a), fl(b), fl(c), y)
    else:
        tx, ty = list(fx), list(fy)
        if reg == 2:
            _need_pos(fx)
            tx = [math.log(x) for x in fx]
        elif reg == 3:
            _need_pos(fy)
            ty = [math.log(y) for y in fy]
        elif reg == 4:
            _need_pos(fy)
            ty = [math.log(y) for y in fy]
        elif reg == 5:
            _need_pos(fx)
            _need_pos(fy)
            tx = [math.log(x) for x in fx]
            ty = [math.log(y) for y in fy]
        elif reg == 6:
            tx = [1 / x for x in fx]
        A, B = _lstsq(tx, ty, 1, ff)
        A, B = fl(A), fl(B)
        r = fl(_corr(tx, ty, ff))
        if reg == 2:
            a, b = A, B
            predict = lambda x: a + b * math.log(x)
            inverse = lambda y: math.exp((y - a) / b)
        elif reg == 3:
            a, b = math.exp(A), B
            predict = lambda x: a * math.exp(b * x)
            inverse = lambda y: math.log(y / a) / b
        elif reg == 4:
            a, b = math.exp(A), math.exp(B)
            predict = lambda x: a * b ** x
            inverse = lambda y: math.log(y / a) / math.log(b)
        elif reg == 5:
            a, b = math.exp(A), B
            predict = lambda x: a * x ** b
            inverse = lambda y: (y / a) ** (1 / b)
        else:
            a, b = A, B
            predict = lambda x: a + b / x
            inverse = lambda y: b / (y - a)
        res += [("a", a), ("b", b), ("r", r)]
    return res, predict, inverse


def max_zero(x):
    return ZERO if r_cmp(x, ZERO) < 0 else x


def _need_pos(v):
    if any(x <= 0 for x in v):
        raise MathErr("Math ERROR (data must be positive)")


def _quad_inv(a, b, c, y):
    d = b * b - 4 * c * (a - y)
    if d < 0:
        raise MathErr("Math ERROR")
    return (-b + math.sqrt(d)) / (2 * c)


# ---------------------------------------------------------------------------
# distributions
# ---------------------------------------------------------------------------
def _ncdf(z):
    return 0.5 * math.erfc(-z / math.sqrt(2))


def normal_pd(x, mu=0.0, sigma=1.0):
    if sigma <= 0:
        raise MathErr("Math ERROR")
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))


def normal_cd(lo, hi, mu=0.0, sigma=1.0):
    if sigma <= 0:
        raise MathErr("Math ERROR")
    return _ncdf((hi - mu) / sigma) - _ncdf((lo - mu) / sigma)


def inv_normal(area, mu=0.0, sigma=1.0):
    if not 0 < area < 1 or sigma <= 0:
        raise MathErr("Math ERROR")
    lo, hi = -40.0, 40.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _ncdf(mid) < area:
            lo = mid
        else:
            hi = mid
    return mu + sigma * (lo + hi) / 2


def binom_pd(k, n, p):
    _chk_binom(k, n, p)
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_cd(k, n, p):
    _chk_binom(k, n, p)
    return min(1.0, sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1)))


def inv_binom(area, n, p):
    if not 0 <= area <= 1:
        raise MathErr("Math ERROR")
    acc = 0.0
    for k in range(n + 1):
        acc += math.comb(n, k) * p ** k * (1 - p) ** (n - k)
        if acc >= area - 1e-12:
            return k
    return n


def _chk_binom(k, n, p):
    if n < 0 or not 0 <= p <= 1 or k < 0 or k > n:
        raise MathErr("Math ERROR")


def poisson_pd(k, lam):
    if lam <= 0 or k < 0:
        raise MathErr("Math ERROR")
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def poisson_cd(k, lam):
    return min(1.0, sum(poisson_pd(i, lam) for i in range(0, k + 1)))


def inv_poisson(area, lam):
    if not 0 <= area < 1:
        raise MathErr("Math ERROR")
    acc, k = 0.0, 0
    while k < 100000:
        acc += poisson_pd(k, lam)
        if acc >= area - 1e-12:
            return k
        k += 1
    raise MathErr("Math ERROR")
