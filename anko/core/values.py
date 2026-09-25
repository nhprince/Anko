"""
Numeric tower used by the Anko engine.

Real values are one of
    Fraction  - exact rational (all integers are Fractions too)
    Exact     - exact sum of  q * sqrt(r) * pi**k  terms  (like the fx-991CW "natural" results)
    float     - inexact decimal

Composite values
    CNum      - complex number whose parts are real values (so 1/2 + sqrt(3)/2 i stays exact)
    Matrix    - list of rows of scalars
    Vec       - list of scalars
"""
from __future__ import annotations

import cmath
import math
from fractions import Fraction

RANGE_LIMIT = 1e100  # like the calculator: results >= 10^100 are a Math ERROR


class MathErr(Exception):
    """Math ERROR"""


class SyntaxErr(Exception):
    """Syntax ERROR"""


class Unsimplifiable(Exception):
    pass


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
_SQ_LIMIT = 10 ** 12


def sqfree(n: int):
    """n = s*s*r with r square free  ->  (s, r)"""
    if n < 0:
        raise ValueError("negative")
    if n < 2:
        return 1, n
    if n > _SQ_LIMIT:
        raise Unsimplifiable
    s, r, m, p = 1, 1, n, 2
    while p * p <= m:
        e = 0
        while m % p == 0:
            m //= p
            e += 1
        if e:
            s *= p ** (e // 2)
            if e % 2:
                r *= p
        p += 1 if p == 2 else 2
    return s, r * m


def iroot(n: int, k: int):
    """floor of the k-th root of a non-negative integer"""
    if n < 2:
        return n
    x = int(round(n ** (1.0 / k)))
    for c in (x - 1, x, x + 1):
        if c >= 0 and c ** k <= n < (c + 1) ** k:
            return c
    lo, hi = 0, 1 << (n.bit_length() // k + 1)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid ** k <= n:
            lo = mid
        else:
            hi = mid - 1
    return lo


def Q(x) -> Fraction:
    return x if isinstance(x, Fraction) else Fraction(x)


# --------------------------------------------------------------------------
# Exact  (sum of q*sqrt(r)*pi^k)
# --------------------------------------------------------------------------
class Exact:
    __slots__ = ("t",)

    def __init__(self, t):
        self.t = t

    def __float__(self):
        return sum(float(c) * math.sqrt(r) * math.pi ** k for (r, k), c in self.t.items())

    def __eq__(self, o):
        return isinstance(o, Exact) and self.t == o.t

    def __hash__(self):
        return hash(frozenset(self.t.items()))

    def __repr__(self):
        return f"Exact({self.t})"


def mk(t: dict):
    t = {k: v for k, v in t.items() if v != 0}
    if not t:
        return Fraction(0)
    if len(t) == 1 and (1, 0) in t:
        return t[(1, 0)]
    return Exact(t)


def terms(x):
    return {(1, 0): x} if isinstance(x, Fraction) else x.t


PI = mk({(1, 1): Fraction(1)})
ZERO = Fraction(0)
ONE = Fraction(1)
I_UNIT = None  # set below (CNum)


def is_real(x):
    return isinstance(x, (Fraction, Exact, float))


def is_exact(x):
    return isinstance(x, (Fraction, Exact))


def fl(x) -> float:
    if isinstance(x, (Fraction, Exact, float, int)):
        return float(x)
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, CNum):
        if is_zero(x.im):
            return fl(x.re)
        raise MathErr("Math ERROR (complex result)")
    raise SyntaxErr("Syntax ERROR")


def is_zero(x, tol=0.0):
    if isinstance(x, Fraction):
        return x == 0
    if isinstance(x, Exact):
        return False
    if isinstance(x, float):
        return abs(x) <= tol
    return False


def sign(x) -> int:
    v = fl(x)
    return (v > 0) - (v < 0)


def check_range(x):
    if isinstance(x, (Fraction, Exact, float)):
        v = fl(x) if not isinstance(x, Fraction) else _frac_mag(x)
        if v != v:
            raise MathErr("Math ERROR")
        if abs(v) >= RANGE_LIMIT and not math.isinf(v) or math.isinf(v):
            raise MathErr("Math ERROR (out of range)")
    elif isinstance(x, CNum):
        check_range(x.re)
        check_range(x.im)
    return x


def _frac_mag(x: Fraction) -> float:
    n, d = abs(x.numerator), x.denominator
    if n.bit_length() > 1000 or d.bit_length() > 1000:
        e = n.bit_length() - d.bit_length()
        return math.ldexp(1.0, min(e, 2000))
    return float(abs(x))


# --------------------------------------------------------------------------
# real arithmetic
# --------------------------------------------------------------------------
def r_add(a, b):
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return a + b
    if isinstance(a, float) or isinstance(b, float):
        return float(a) + float(b)
    t = dict(terms(a))
    for k, v in terms(b).items():
        t[k] = t.get(k, 0) + v
    return mk(t)


def r_neg(a):
    if isinstance(a, (Fraction, float)):
        return -a
    return Exact({k: -v for k, v in a.t.items()})


def r_sub(a, b):
    return r_add(a, r_neg(b))


def r_mul(a, b):
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return a * b
    if isinstance(a, float) or isinstance(b, float):
        return float(a) * float(b)
    if isinstance(b, Fraction):
        return mk({k: v * b for k, v in a.t.items()})
    if isinstance(a, Fraction):
        return mk({k: v * a for k, v in b.t.items()})
    try:
        out = {}
        for (r1, k1), c1 in a.t.items():
            for (r2, k2), c2 in b.t.items():
                s, r = sqfree(r1 * r2)
                key = (r, k1 + k2)
                out[key] = out.get(key, 0) + c1 * c2 * s
        return mk(out)
    except Unsimplifiable:
        return float(a) * float(b)


def r_inv(b):
    if isinstance(b, Fraction):
        if b == 0:
            raise MathErr("Math ERROR (divide by zero)")
        return 1 / b
    if isinstance(b, float):
        if b == 0:
            raise MathErr("Math ERROR (divide by zero)")
        return 1.0 / b
    if len(b.t) == 1:
        (r, k), c = next(iter(b.t.items()))
        return mk({(r, -k): 1 / (c * r)})
    if len(b.t) == 2:
        (t1, c1), (t2, c2) = b.t.items()
        conj = Exact({t1: c1, t2: -c2})
        den = r_mul(b, conj)
        if isinstance(den, Fraction) or (isinstance(den, Exact) and len(den.t) == 1):
            return r_mul(conj, r_inv(den))
    return 1.0 / float(b)


def r_div(a, b):
    if isinstance(a, float) or isinstance(b, float):
        if float(b) == 0:
            raise MathErr("Math ERROR (divide by zero)")
        return float(a) / float(b)
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        if b == 0:
            raise MathErr("Math ERROR (divide by zero)")
        return a / b
    return r_mul(a, r_inv(b))


def r_cmp(a, b) -> int:
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return (a > b) - (a < b)
    x, y = float(a), float(b)
    if abs(x - y) <= 1e-12 * max(1.0, abs(x), abs(y)):
        return 0
    return (x > y) - (x < y)


def r_sqrt(a):
    """exact square root of a non-negative real if possible"""
    if isinstance(a, Fraction):
        if a < 0:
            raise MathErr("Math ERROR")
        try:
            s, r = sqfree(a.numerator * a.denominator)
        except Unsimplifiable:
            return math.sqrt(a)
        return mk({(r, 0): Fraction(s, a.denominator)})
    if isinstance(a, float):
        if a < 0:
            raise MathErr("Math ERROR")
        return math.sqrt(a)
    # Exact: c * pi^k  with even k  -> sqrt of coefficient * pi^(k/2)
    if len(a.t) == 1:
        (r, k), c = next(iter(a.t.items()))
        if c > 0 and k % 2 == 0:
            try:
                s, rr = sqfree(int(c.numerator * c.denominator) * r)
            except Unsimplifiable:
                return math.sqrt(float(a))
            return mk({(rr, k // 2): Fraction(s, c.denominator)})
    v = float(a)
    if v < 0:
        raise MathErr("Math ERROR")
    return math.sqrt(v)


def r_pow(a, b, allow_complex=False):
    """real ** real. May return CNum when allow_complex and result is not real"""
    if isinstance(b, Fraction) and b.denominator == 1:
        n = b.numerator
        if isinstance(a, Fraction):
            if a == 0:
                if n <= 0:
                    raise MathErr("Math ERROR")
                return Fraction(0)
            if abs(n) * (a.numerator.bit_length() + a.denominator.bit_length()) > 5000 and abs(a) not in (0, 1):
                raise MathErr("Math ERROR (out of range)")
            return a ** n
        if isinstance(a, Exact):
            if abs(n) > 40:
                return _fpow(float(a), float(n))
            base = a if n >= 0 else r_inv(a)
            res = ONE
            for _ in range(abs(n)):
                res = r_mul(res, base)
            return res
        return _fpow(a, float(n))
    if isinstance(b, Fraction) and isinstance(a, Fraction):
        p, q = b.numerator, b.denominator
        if a > 0:
            if q == 2:
                return r_mul(r_sqrt(a), r_pow(a, Fraction((p - 1) // 2)))
            nr, dr = iroot(a.numerator, q), iroot(a.denominator, q)
            if nr ** q == a.numerator and dr ** q == a.denominator:
                return Fraction(nr, dr) ** p
        elif a < 0:
            if q % 2 == 1:
                res = r_pow(-a, b)
                return r_neg(res) if p % 2 else res
            if not allow_complex:
                raise MathErr("Math ERROR")
    x, y = float(a), float(b)
    if x < 0:
        if not allow_complex:
            raise MathErr("Math ERROR")
        return c_from_py(complex(x) ** y)
    return _fpow(x, y)


def _fpow(x, y):
    try:
        if x == 0 and y <= 0:
            raise MathErr("Math ERROR")
        return float(x) ** float(y)
    except OverflowError:
        raise MathErr("Math ERROR (out of range)")


# --------------------------------------------------------------------------
# Complex
# --------------------------------------------------------------------------
class CNum:
    __slots__ = ("re", "im")

    def __init__(self, re, im):
        self.re, self.im = re, im

    def __repr__(self):
        return f"CNum({self.re!r}, {self.im!r})"

    def __eq__(self, o):
        return isinstance(o, CNum) and r_cmp(self.re, o.re) == 0 and r_cmp(self.im, o.im) == 0

    def __hash__(self):
        return hash((float(self.re), float(self.im)))

    def to_py(self):
        return complex(fl(self.re), fl(self.im))


I_UNIT = CNum(ZERO, ONE)


def cnorm(re, im):
    return re if is_zero(im) else CNum(re, im)


def cparts(x):
    if isinstance(x, CNum):
        return x.re, x.im
    return x, ZERO


def c_from_py(z: complex):
    re, im = z.real, z.imag
    m = max(abs(re), abs(im))
    if m:
        if abs(im) < 1e-14 * m:
            im = 0.0
        if abs(re) < 1e-14 * m:
            re = 0.0
    return cnorm(re, im) if im != 0 else re


def c_abs(z: CNum):
    return r_sqrt(r_add(r_mul(z.re, z.re), r_mul(z.im, z.im)))


def c_arg_float(z) -> float:
    re, im = cparts(z)
    return math.atan2(fl(im), fl(re))


def c_mul(a, b):
    ar, ai = cparts(a)
    br, bi = cparts(b)
    return cnorm(r_sub(r_mul(ar, br), r_mul(ai, bi)), r_add(r_mul(ar, bi), r_mul(ai, br)))


def c_div(a, b):
    ar, ai = cparts(a)
    br, bi = cparts(b)
    den = r_add(r_mul(br, br), r_mul(bi, bi))
    if is_zero(den):
        raise MathErr("Math ERROR (divide by zero)")
    re = r_div(r_add(r_mul(ar, br), r_mul(ai, bi)), den)
    im = r_div(r_sub(r_mul(ai, br), r_mul(ar, bi)), den)
    return cnorm(re, im)


def c_pow(a, b):
    br, bi = cparts(b)
    if isinstance(br, Fraction) and br.denominator == 1 and is_zero(bi) and abs(br) <= 200:
        n = br.numerator
        base = a if n >= 0 else c_div(ONE, a)
        res = ONE
        for _ in range(abs(n)):
            res = c_mul(res, base)
        return res
    x, y = complex(fl(cparts(a)[0]), fl(cparts(a)[1])), complex(fl(br), fl(bi))
    if x == 0:
        if y.real <= 0:
            raise MathErr("Math ERROR")
        return ZERO
    return c_from_py(x ** y)


# --------------------------------------------------------------------------
# Matrix / Vector
# --------------------------------------------------------------------------
class Matrix:
    def __init__(self, rows):
        self.rows = [list(r) for r in rows]

    @property
    def shape(self):
        return len(self.rows), (len(self.rows[0]) if self.rows else 0)

    def __eq__(self, o):
        return isinstance(o, Matrix) and self.shape == o.shape and all(
            eq(a, b) for r1, r2 in zip(self.rows, o.rows) for a, b in zip(r1, r2))

    def __repr__(self):
        return f"Matrix({self.rows})"


class Vec:
    def __init__(self, v):
        self.v = list(v)

    def __eq__(self, o):
        return isinstance(o, Vec) and len(self.v) == len(o.v) and all(eq(a, b) for a, b in zip(self.v, o.v))

    def __repr__(self):
        return f"Vec({self.v})"


def eq(a, b):
    if isinstance(a, (Matrix, Vec)) or isinstance(b, (Matrix, Vec)):
        return a == b
    if isinstance(a, CNum) or isinstance(b, CNum):
        ar, ai = cparts(a)
        br, bi = cparts(b)
        return r_cmp(ar, br) == 0 and r_cmp(ai, bi) == 0
    return r_cmp(a, b) == 0


# --------------------------------------------------------------------------
# generic scalar dispatch
# --------------------------------------------------------------------------
def _coerce(x):
    if isinstance(x, bool):
        return Fraction(int(x))
    if isinstance(x, int):
        return Fraction(x)
    return x


def add(a, b):
    a, b = _coerce(a), _coerce(b)
    if isinstance(a, (Matrix, Vec)) or isinstance(b, (Matrix, Vec)):
        return _la_elementwise(a, b, add)
    if isinstance(a, CNum) or isinstance(b, CNum):
        (ar, ai), (br, bi) = cparts(a), cparts(b)
        return cnorm(r_add(ar, br), r_add(ai, bi))
    return r_add(a, b)


def neg(a):
    a = _coerce(a)
    if isinstance(a, Matrix):
        return Matrix([[neg(x) for x in r] for r in a.rows])
    if isinstance(a, Vec):
        return Vec([neg(x) for x in a.v])
    if isinstance(a, CNum):
        return CNum(r_neg(a.re), r_neg(a.im))
    return r_neg(a)


def sub(a, b):
    return add(a, neg(b))


def mul(a, b):
    a, b = _coerce(a), _coerce(b)
    if isinstance(a, (Matrix, Vec)) or isinstance(b, (Matrix, Vec)):
        return _la_mul(a, b)
    if isinstance(a, CNum) or isinstance(b, CNum):
        return c_mul(a, b)
    return r_mul(a, b)


def div(a, b):
    a, b = _coerce(a), _coerce(b)
    if isinstance(b, (Matrix, Vec)):
        if isinstance(b, Matrix) and isinstance(a, Matrix):
            return mul(a, mat_inv(b))
        raise MathErr("Math ERROR")
    if isinstance(a, Matrix):
        return Matrix([[div(x, b) for x in r] for r in a.rows])
    if isinstance(a, Vec):
        return Vec([div(x, b) for x in a.v])
    if isinstance(a, CNum) or isinstance(b, CNum):
        return c_div(a, b)
    return r_div(a, b)


def power(a, b, allow_complex=False):
    a, b = _coerce(a), _coerce(b)
    if isinstance(a, Matrix):
        if isinstance(b, Fraction) and b.denominator == 1:
            n = b.numerator
            if a.shape[0] != a.shape[1]:
                raise MathErr("Math ERROR (dimension)")
            base = a if n >= 0 else mat_inv(a)
            res = mat_identity(a.shape[0])
            for _ in range(min(abs(n), 200)):
                res = mul(res, base)
            return res
        raise MathErr("Math ERROR")
    if isinstance(a, Vec) or isinstance(b, (Matrix, Vec)):
        raise MathErr("Math ERROR")
    if isinstance(a, CNum) or isinstance(b, CNum):
        return c_pow(a, b)
    return r_pow(a, b, allow_complex)


def _la_elementwise(a, b, f):
    if isinstance(a, Matrix) and isinstance(b, Matrix):
        if a.shape != b.shape:
            raise MathErr("Dimension ERROR")
        return Matrix([[f(x, y) for x, y in zip(r1, r2)] for r1, r2 in zip(a.rows, b.rows)])
    if isinstance(a, Vec) and isinstance(b, Vec):
        if len(a.v) != len(b.v):
            raise MathErr("Dimension ERROR")
        return Vec([f(x, y) for x, y in zip(a.v, b.v)])
    raise MathErr("Math ERROR (cannot add scalar and matrix/vector)")


def _la_mul(a, b):
    if isinstance(a, Matrix) and isinstance(b, Matrix):
        n, m = a.shape
        m2, p = b.shape
        if m != m2:
            raise MathErr("Dimension ERROR")
        out = []
        for i in range(n):
            row = []
            for j in range(p):
                s = ZERO
                for k in range(m):
                    s = add(s, mul(a.rows[i][k], b.rows[k][j]))
                row.append(s)
            out.append(row)
        return Matrix(out)
    if isinstance(a, Matrix) and isinstance(b, Vec):
        raise MathErr("Math ERROR")
    if isinstance(a, Vec) and isinstance(b, Vec):
        raise MathErr("Math ERROR (use dot/cross)")
    if isinstance(a, (Matrix, Vec)):
        a, b = b, a  # scalar * M
    if isinstance(b, Matrix):
        return Matrix([[mul(a, x) for x in r] for r in b.rows])
    if isinstance(b, Vec):
        return Vec([mul(a, x) for x in b.v])
    raise MathErr("Math ERROR")


def mat_identity(n):
    return Matrix([[ONE if i == j else ZERO for j in range(n)] for i in range(n)])


def _near_zero(x):
    if isinstance(x, float):
        return abs(x) < 1e-12
    if isinstance(x, CNum):
        return _near_zero(x.re) and _near_zero(x.im)
    return is_zero(x)


def mat_trn(m: Matrix):
    return Matrix([list(c) for c in zip(*m.rows)])


def mat_det(m: Matrix):
    n, c = m.shape
    if n != c:
        raise MathErr("Dimension ERROR")
    a = [list(r) for r in m.rows]
    det = ONE
    for i in range(n):
        p = next((r for r in range(i, n) if not _near_zero(a[r][i])), None)
        if p is None:
            return ZERO
        if p != i:
            a[i], a[p] = a[p], a[i]
            det = neg(det)
        det = mul(det, a[i][i])
        for r in range(i + 1, n):
            f = div(a[r][i], a[i][i])
            for cc in range(i, n):
                a[r][cc] = sub(a[r][cc], mul(f, a[i][cc]))
    return det


def mat_rref(m: Matrix, augment_cols=0):
    a = [list(r) for r in m.rows]
    rows, cols = len(a), len(a[0])
    lead = 0
    limit = cols - augment_cols
    for r in range(rows):
        if lead >= limit:
            break
        i = r
        while _near_zero(a[i][lead]):
            i += 1
            if i == rows:
                i = r
                lead += 1
                if lead == limit:
                    return Matrix(a)
        a[i], a[r] = a[r], a[i]
        pv = a[r][lead]
        a[r] = [div(x, pv) for x in a[r]]
        for j in range(rows):
            if j != r and not _near_zero(a[j][lead]):
                f = a[j][lead]
                a[j] = [sub(x, mul(f, y)) for x, y in zip(a[j], a[r])]
        lead += 1
    return Matrix(a)


def mat_inv(m: Matrix):
    n, c = m.shape
    if n != c:
        raise MathErr("Dimension ERROR")
    if _near_zero(mat_det(m)):
        raise MathErr("Math ERROR (singular matrix)")
    aug = Matrix([list(r) + [ONE if i == j else ZERO for j in range(n)] for i, r in enumerate(m.rows)])
    red = mat_rref(aug, augment_cols=n)
    return Matrix([r[n:] for r in red.rows])


def vec_dot(a: Vec, b: Vec):
    if len(a.v) != len(b.v):
        raise MathErr("Dimension ERROR")
    s = ZERO
    for x, y in zip(a.v, b.v):
        s = add(s, mul(x, y))
    return s


def vec_cross(a: Vec, b: Vec):
    if len(a.v) != 3 or len(b.v) != 3:
        raise MathErr("Dimension ERROR")
    x1, y1, z1 = a.v
    x2, y2, z2 = b.v
    return Vec([sub(mul(y1, z2), mul(z1, y2)), sub(mul(z1, x2), mul(x1, z2)), sub(mul(x1, y2), mul(y1, x2))])


def vec_norm(a: Vec):
    s = ZERO
    for x in a.v:
        s = add(s, mul(x, x))
    return r_sqrt(s) if is_real(s) else math.sqrt(fl(s))
