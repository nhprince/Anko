"""Equation and inequality solving (simultaneous linear, polynomial degree 2-4, inequalities)."""
from __future__ import annotations

import cmath
import math
from fractions import Fraction

from .values import (CNum, Exact, Matrix, MathErr, ZERO, ONE, add, sub, mul, div, neg, fl, is_real,
                     mat_rref, mat_det, r_add, r_sub, r_mul, r_div, r_neg, r_sqrt, r_cmp, cnorm, c_from_py,
                     _near_zero)
from .numeric import tidy


# ---------------------------------------------------------------------------
# simultaneous linear equations
# ---------------------------------------------------------------------------
def solve_linear(rows):
    """rows: n rows of n coefficients + constant  ->  list of n solutions"""
    n = len(rows)
    m = Matrix(rows)
    if _near_zero(mat_det(Matrix([r[:n] for r in rows]))):
        raise MathErr("No Solution / Infinite solutions")
    red = mat_rref(m, augment_cols=1)
    return [red.rows[i][n] for i in range(n)]


# ---------------------------------------------------------------------------
# polynomial roots
# ---------------------------------------------------------------------------
def _divisors(n: int):
    n = abs(n)
    out = set()
    i = 1
    while i * i <= n:
        if n % i == 0:
            out.add(i)
            out.add(n // i)
        i += 1
    return sorted(out)


def _horner(coefs, x):
    r = ZERO
    for c in coefs:
        r = r * x + c
    return r


def _deflate(coefs, root):
    out = [coefs[0]]
    for c in coefs[1:-1]:
        out.append(c + out[-1] * root)
    return out


def _quadratic(a, b, c):
    """exact/float quadratic; returns [x1, x2]"""
    disc = r_sub(r_mul(b, b), r_mul(Fraction(4), r_mul(a, c)))
    two_a = r_mul(Fraction(2), a)
    nb = r_neg(b)
    if r_cmp(disc, ZERO) >= 0:
        s = r_sqrt(disc)
        return [r_div(r_add(nb, s), two_a), r_div(r_sub(nb, s), two_a)]
    s = r_sqrt(r_neg(disc))
    re = r_div(nb, two_a)
    im = r_div(s, two_a)
    return [cnorm(re, im), cnorm(re, r_neg(im))]


def _durand_kerner(coefs):
    cs = [complex(fl(c)) for c in coefs]
    n = len(cs) - 1
    cs = [c / cs[0] for c in cs]
    r = 1 + max(abs(c) for c in cs[1:])
    roots = [complex(0.4, 0.9) ** k * r * 0.5 for k in range(n)]
    for _ in range(500):
        new = []
        for i, z in enumerate(roots):
            p = 0
            for c in cs:
                p = p * z + c
            d = 1
            for j, w in enumerate(roots):
                if i != j:
                    d *= (z - w)
            if d == 0:
                d = 1e-12
            new.append(z - p / d)
        delta = max(abs(a - b) for a, b in zip(new, roots))
        roots = new
        if delta < 1e-15:
            break
    # polish with Newton
    out = []
    for z in roots:
        for _ in range(5):
            p = dp = 0
            for c in cs:
                dp = dp * z + p
                p = p * z + c
            if dp != 0:
                z = z - p / dp
        if abs(z.imag) < 1e-9 * max(1, abs(z.real)):
            z = complex(z.real, 0)
        out.append(z)
    return out


def solve_poly(coefs):
    """coefs highest degree first (length 3..5) -> list of roots"""
    while coefs and is_real(coefs[0]) and r_cmp(coefs[0], ZERO) == 0:
        coefs = coefs[1:]
    deg = len(coefs) - 1
    if deg < 1:
        raise MathErr("Math ERROR")
    exact_rational = all(isinstance(c, Fraction) for c in coefs)
    roots = []
    cs = list(coefs)
    if exact_rational:
        # rational root theorem on the integer version of the polynomial
        while len(cs) - 1 > 2:
            lcm = 1
            for c in cs:
                lcm = lcm * c.denominator // math.gcd(lcm, c.denominator)
            ints = [int(c * lcm) for c in cs]
            # strip zero roots
            if ints[-1] == 0:
                roots.append(ZERO)
                cs = cs[:-1]
                continue
            found = None
            if abs(ints[0]) < 10 ** 9 and abs(ints[-1]) < 10 ** 9:
                for p in _divisors(ints[-1]):
                    for q in _divisors(ints[0]):
                        for sgn in (1, -1):
                            cand = Fraction(sgn * p, q)
                            if _horner(cs, cand) == 0:
                                found = cand
                                break
                        if found is not None:
                            break
                    if found is not None:
                        break
            if found is None:
                break
            roots.append(found)
            cs = _deflate(cs, found)
    if len(cs) - 1 == 2:
        roots.extend(_quadratic(*cs))
    elif len(cs) - 1 == 1:
        roots.append(r_div(r_neg(cs[1]), cs[0]))
    elif len(cs) - 1 > 2:
        for z in _durand_kerner(cs):
            roots.append(tidy(z.real) if z.imag == 0 else cnorm(tidy(z.real), tidy(z.imag)))
    key = lambda r: (fl(r.re) if isinstance(r, CNum) else fl(r), 1 if isinstance(r, CNum) else 0,
                     -fl(r.im) if isinstance(r, CNum) else 0)
    return sorted(roots, key=key)


# ---------------------------------------------------------------------------
# inequalities
# ---------------------------------------------------------------------------
def solve_inequality(coefs, op):
    """returns list of ranges  (lo, lo_incl, hi, hi_incl) with lo/hi = None for infinity, or 'ALL'/'NONE'"""
    roots = [r for r in solve_poly(list(coefs)) if not isinstance(r, CNum)]
    uniq = []
    for r in sorted(roots, key=fl):
        if not uniq or abs(fl(r) - fl(uniq[-1])) > 1e-9:
            uniq.append(r)
    fs = [fl(c) for c in coefs]

    def p(x):
        v = 0.0
        for c in fs:
            v = v * x + c
        return v

    def ok(val, strict_zero):
        if op == ">":
            return val > 1e-12
        if op == "<":
            return val < -1e-12
        if op == "≥":
            return val >= -1e-12
        return val <= 1e-12

    k = len(uniq)
    xs = [fl(r) for r in uniq]
    probes = []
    if k == 0:
        probes = [(0.0, "open")]
    else:
        pts = [xs[0] - 1] + [(xs[i] + xs[i + 1]) / 2 for i in range(k - 1)] + [xs[-1] + 1]
    atoms = []  # (satisfied, kind, index)
    if k == 0:
        return "ALL" if ok(p(0.0), False) else "NONE"
    for i in range(k + 1):
        atoms.append((ok(p(pts[i]), False), "int", i))
        if i < k:
            atoms.append((ok(0.0, True) if op in ("≥", "≤") else False, "pt", i))
    # merge consecutive satisfied atoms
    ranges = []
    cur = None
    for idx, (sat, kind, i) in enumerate(atoms):
        if sat:
            if cur is None:
                cur = [idx, idx]
            else:
                cur[1] = idx
        elif cur is not None:
            ranges.append(cur)
            cur = None
    if cur is not None:
        ranges.append(cur)
    if not ranges:
        return "NONE"
    out = []
    for a, b in ranges:
        ka, ia = atoms[a][1], atoms[a][2]
        kb, ib = atoms[b][1], atoms[b][2]
        if ka == "int":
            lo, lo_in = (None, False) if ia == 0 else (uniq[ia - 1], False)
        else:
            lo, lo_in = uniq[ia], True
        if kb == "int":
            hi, hi_in = (None, False) if ib == k else (uniq[ib], False)
        else:
            hi, hi_in = uniq[ib], True
        out.append((lo, lo_in, hi, hi_in))
    if len(out) == 1 and out[0][0] is None and out[0][2] is None:
        return "ALL"
    return out
