"""The calculation engine (no GUI code in here)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field, asdict
from fractions import Fraction
from functools import reduce

from . import numeric as num
from .parser import parse, free_vars
from .values import *  # noqa: F401,F403
from .values import (MathErr, SyntaxErr, CNum, Matrix, Vec, Exact, PI, ZERO, ONE, I_UNIT, add, sub, mul, div,
                     neg, power, fl, is_real, is_exact, r_sqrt, r_pow, r_mul, r_div, r_add, r_sub, r_neg,
                     cnorm, cparts, c_abs, c_mul, c_from_py, check_range, Q, mat_det, mat_inv, mat_trn,
                     mat_identity, mat_rref, vec_dot, vec_cross, vec_norm, r_cmp, eq)

MAX_LOOP = 300000


@dataclass
class Settings:
    angle: str = "DEG"            # DEG | RAD | GRA
    notation: str = "norm1"       # norm1 | norm2 | fix | sci | eng
    digits: int = 10              # significant digits (norm/sci/eng) or decimals (fix)
    style: str = "math"           # math (exact when possible) | decimal
    complex_fmt: str = "rect"     # rect (a+bi) | polar (r∠θ)
    mixed: bool = False           # show improper fractions as mixed numbers
    thousands: bool = False
    theme: str = "dark"
    sound: bool = False

    def to_json(self):
        return asdict(self)

    @staticmethod
    def from_json(d):
        s = Settings()
        for k, v in (d or {}).items():
            if hasattr(s, k):
                setattr(s, k, v)
        return s


class DMSVal:
    """a value shown as degrees/minutes/seconds"""

    def __init__(self, deg):
        self.deg = deg


class PairVal:
    """result of Pol( / Rec(  – two named values"""

    def __init__(self, names, vals):
        self.names, self.vals = names, vals


VARS = list("ABCDEFXYM")


class Interp:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or Settings()
        self.vars = {n: ZERO for n in VARS}
        self.ans = ZERO
        self.preans = ZERO
        self.mats = {k: None for k in "ABCD"}
        self.vecs = {k: None for k in "ABCD"}
        self.matans = None
        self.vctans = None
        self.complex_mode = False
        self.functions = {}   # user f(x), g(x) : name -> ast
        self._depth = 0
        self.sheet_cb = None  # spreadsheet hook: (name, args) -> value

    # ------------------------------------------------------------------
    def evaluate(self, text: str, record=True, env=None, allow_assign=True):
        ast = parse(text, allow_assign=allow_assign)
        v = self.eval_ast(ast, env or {})
        if record:
            self.record(v)
        return v

    def record(self, v):
        if isinstance(v, (bool, PairVal)):
            return
        self.preans, self.ans = self.ans, v
        if isinstance(v, Matrix):
            self.matans = v
        elif isinstance(v, Vec):
            self.vctans = v

    def reset_memory(self):
        self.vars = {n: ZERO for n in VARS}
        self.ans = self.preans = ZERO
        self.mats = {k: None for k in "ABCD"}
        self.vecs = {k: None for k in "ABCD"}

    # ------------------------------------------------------------------
    def eval_ast(self, n, env):
        self._depth += 1
        if self._depth > 400:
            self._depth = 0
            raise MathErr("Stack ERROR")
        try:
            return self._eval(n, env)
        finally:
            self._depth = max(0, self._depth - 1)

    def _eval(self, n, env):
        k = n[0]
        if k == "num":
            return n[1]
        if k == "var":
            name = n[1]
            if name in env:
                return env[name]
            if name == "x":
                return ZERO
            if name == "theta":
                return ZERO
            return self.vars[name]
        if k == "const":
            return self._const(n[1])
        if k == "neg":
            return neg(self.eval_ast(n[1], env))
        if k == "bin":
            op = n[1]
            if op == "^" and n[2] == ("const", "e"):
                return check_range(self.call_values("exp", [self.eval_ast(n[3], env)]))
            a = self.eval_ast(n[2], env)
            b = self.eval_ast(n[3], env)
            if op == "+":
                r = add(a, b)
            elif op == "-":
                r = sub(a, b)
            elif op == "*":
                r = mul(a, b)
            elif op == "/":
                r = div(a, b)
            else:
                r = power(a, b, self.complex_mode)
            return check_range(r)
        if k == "cmp":
            a = self.eval_ast(n[2], env)
            b = self.eval_ast(n[3], env)
            op = n[1]
            if op == "=":
                return eq(a, b)
            if op == "≠":
                return not eq(a, b)
            c = r_cmp(a, b)
            return {"<": c < 0, ">": c > 0, "≤": c <= 0, "≥": c >= 0}[op]
        if k == "fact":
            return self._fact(self.eval_ast(n[1], env))
        if k == "pct":
            return div(self.eval_ast(n[1], env), Fraction(100))
        if k == "deg":
            return self._deg_to_unit(self.eval_ast(n[1], env))
        if k == "dms":
            d = self.eval_ast(n[1], env)
            m = n[2] if n[2] is not None else ZERO
            s = n[3] if n[3] is not None else ZERO
            total = add(add(d, div(m, Fraction(60))), div(s, Fraction(3600)))
            return self._deg_to_unit(total)
        if k == "polar":
            r = self.eval_ast(n[1], env)
            th = self.eval_ast(n[2], env)
            u = self.s.angle
            return cnorm(mul(r, num.trig("cos", th, u)), mul(r, num.trig("sin", th, u)))
        if k == "sto":
            v = self.eval_ast(n[1], env)
            self._store(n[2], v)
            return v
        if k == "call":
            return self._call(n[1], n[2], env)
        raise SyntaxErr("Syntax ERROR")

    # ------------------------------------------------------------------
    def _const(self, name):
        if name == "pi":
            return PI
        if name == "e":
            return math.e
        if name == "i":
            if not self.complex_mode:
                raise MathErr("Math ERROR: use the Complex mode for i")
            return I_UNIT
        if name == "ans":
            return self.ans
        if name == "preans":
            return self.preans
        if name == "ran#":
            return random.randint(0, 999) / 1000
        if name == "matans":
            if self.matans is None:
                raise MathErr("Math ERROR: no MatAns yet")
            return self.matans
        if name == "vctans":
            if self.vctans is None:
                raise MathErr("Math ERROR: no VctAns yet")
            return self.vctans
        if name.startswith("mat"):
            m = self.mats[name[-1].upper()]
            if m is None:
                raise MathErr(f"Math ERROR: Mat{name[-1].upper()} is not defined")
            return m
        if name.startswith("vct"):
            v = self.vecs[name[-1].upper()]
            if v is None:
                raise MathErr(f"Math ERROR: Vct{name[-1].upper()} is not defined")
            return v
        raise SyntaxErr("Syntax ERROR")

    def _store(self, name, v):
        if name in self.vars:
            if isinstance(v, (Matrix, Vec, bool)):
                raise MathErr("Math ERROR")
            self.vars[name] = v
        elif name.startswith("mat"):
            if not isinstance(v, Matrix):
                raise MathErr("Math ERROR")
            self.mats[name[-1].upper()] = v
        elif name.startswith("vct"):
            if not isinstance(v, Vec):
                raise MathErr("Math ERROR")
            self.vecs[name[-1].upper()] = v
        else:
            raise SyntaxErr("Syntax ERROR")

    def _deg_to_unit(self, x):
        u = self.s.angle
        if u == "DEG":
            return x
        if u == "GRA":
            return mul(x, Fraction(10, 9))
        return mul(x, r_div(PI, Fraction(180)))

    def _to_deg(self, x):
        """value in current angle unit -> degrees (exact if possible)"""
        d = num.angle_to_degrees_exact(x, self.s.angle)
        if d is not None:
            return d
        return num.from_radians(num.to_radians(fl(x), self.s.angle), "DEG")

    # ------------------------------------------------------------------
    def _fact(self, x):
        if isinstance(x, float) and x == int(x):
            x = Fraction(int(x))
        if not isinstance(x, Fraction) or x.denominator != 1 or x < 0 or x > 170:
            raise MathErr("Math ERROR")
        return check_range(Fraction(math.factorial(int(x))))

    def _int(self, x, lo=None, hi=None):
        if isinstance(x, float) and x == int(x):
            x = Fraction(int(x))
        if not isinstance(x, Fraction) or x.denominator != 1:
            raise MathErr("Math ERROR")
        v = int(x)
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            raise MathErr("Math ERROR")
        return v

    def _real(self, x):
        if not is_real(x):
            raise MathErr("Math ERROR")
        return x

    def _flat(self, args):
        out = []
        for a in args:
            if isinstance(a, list):
                out.extend(a)
            elif isinstance(a, Vec):
                out.extend(a.v)
            elif isinstance(a, Matrix):
                for r in a.rows:
                    out.extend(r)
            else:
                out.append(a)
        return out

    def make_fn(self, ast, var="x", env=None):
        base = dict(env or {})

        def f(v):
            e = dict(base)
            e[var] = v
            return fl(self.eval_ast(ast, e))
        return f

    # ------------------------------------------------------------------
    def _call(self, name, args, env):
        # lazily evaluated forms ------------------------------------------------
        if name == "integ":
            if len(args) != 3:
                raise SyntaxErr("Syntax ERROR")
            a, b = fl(self.eval_ast(args[1], env)), fl(self.eval_ast(args[2], env))
            return num.integrate(self.make_fn(args[0], "x", env), a, b)
        if name == "deriv":
            if len(args) != 2:
                raise SyntaxErr("Syntax ERROR")
            a = fl(self.eval_ast(args[1], env))
            return num.derivative(self.make_fn(args[0], "x", env), a)
        if name in ("sigma", "prod"):
            if len(args) != 4 or args[1][0] != "var":
                raise SyntaxErr("Syntax ERROR")
            var = args[1][1]
            lo = self._int(self.eval_ast(args[2], env))
            hi = self._int(self.eval_ast(args[3], env))
            if hi - lo > MAX_LOOP:
                raise MathErr("Time Out")
            acc = ZERO if name == "sigma" else ONE
            for k in range(lo, hi + 1):
                e = dict(env)
                e[var] = Fraction(k)
                v = self.eval_ast(args[0], e)
                acc = add(acc, v) if name == "sigma" else mul(acc, v)
                check_range(acc)
            return acc
        vals = [self.eval_ast(a, env) for a in args]
        return self.call_values(name, vals)

    def call_values(self, name, v):
        u = self.s.angle
        n = len(v)

        def need(k):
            if n != k:
                raise SyntaxErr("Syntax ERROR")

        # ---- trig ------------------------------------------------------------
        if name in ("sin", "cos", "tan"):
            need(1)
            if isinstance(v[0], CNum):
                z = v[0].to_py()
                return c_from_py({"sin": __import__("cmath").sin, "cos": __import__("cmath").cos,
                                  "tan": __import__("cmath").tan}[name](z))
            return num.trig(name, self._real(v[0]), u)
        if name in ("asin", "acos", "atan"):
            need(1)
            x = self._real(v[0])
            if name != "atan" and abs(fl(x)) > 1 and self.complex_mode:
                import cmath
                return c_from_py(getattr(cmath, name)(fl(x)))
            return num.inv_trig(name, x, u)
        if name in ("sinh", "cosh", "tanh", "asinh", "acosh", "atanh"):
            need(1)
            x = fl(self._real(v[0]))
            try:
                return getattr(math, name)(x)
            except (ValueError, OverflowError):
                raise MathErr("Math ERROR")
        # ---- logs / exp ------------------------------------------------------
        if name in ("log", "log10", "logb", "log2", "ln"):
            if name == "ln":
                need(1)
                return self._ln(v[0])
            if name == "log" and n == 1 or name == "log10":
                need(1)
                return self._log(Fraction(10), v[0])
            if name == "log2":
                need(1)
                return self._log(Fraction(2), v[0])
            need(2)
            return self._log(self._real(v[0]), v[1])
        if name == "exp":
            need(1)
            if isinstance(v[0], Fraction) and v[0] == 0:
                return ONE
            if isinstance(v[0], CNum):
                import cmath
                re, im = v[0].re, v[0].im
                if num.angle_to_degrees_exact(im, "RAD") is not None:
                    mag = ONE if (isinstance(re, Fraction) and re == 0) else math.exp(fl(re))
                    return cnorm(mul(mag, num.trig("cos", im, "RAD")), mul(mag, num.trig("sin", im, "RAD")))
                return c_from_py(cmath.exp(v[0].to_py()))
            try:
                return check_range(math.exp(fl(v[0])))
            except OverflowError:
                raise MathErr("Math ERROR")
        # ---- roots / abs -----------------------------------------------------
        if name == "sqrt":
            need(1)
            return self._sqrt(v[0])
        if name == "cbrt":
            need(1)
            return r_pow(self._real(v[0]), Fraction(1, 3))
        if name == "root":
            need(2)
            n_, x = self._real(v[0]), self._real(v[1])
            if r_cmp(n_, ZERO) == 0:
                raise MathErr("Math ERROR")
            return power(x, r_div(ONE, n_), self.complex_mode)
        if name == "abs":
            need(1)
            x = v[0]
            if isinstance(x, CNum):
                return c_abs(x)
            if isinstance(x, Vec):
                return vec_norm(x)
            if isinstance(x, Matrix):
                raise MathErr("Math ERROR")
            return x if r_cmp(x, ZERO) >= 0 else r_neg(x)
        if name == "norm":
            need(1)
            if not isinstance(v[0], Vec):
                raise MathErr("Math ERROR")
            return vec_norm(v[0])
        if name == "sign":
            need(1)
            return Fraction(int(math.copysign(1, fl(v[0]))) if fl(v[0]) != 0 else 0)
        if name == "pow":
            need(2)
            return power(v[0], v[1], self.complex_mode)
        # ---- rounding --------------------------------------------------------
        if name in ("floor", "ceil", "int", "frac"):
            need(1)
            x = self._real(v[0])
            f = fl(x) if not isinstance(x, Fraction) else x
            if name == "floor":
                r = math.floor(f)
            elif name == "ceil":
                r = math.ceil(f)
            else:
                r = math.trunc(f)
            if name == "frac":
                return sub(x, Fraction(r))
            return Fraction(r)
        if name in ("round", "rnd"):
            x = self._real(v[0])
            digits = self._int(v[1]) if n > 1 else None
            fx = fl(x)
            if digits is None:
                return float(f"{fx:.{max(self.s.digits, 1) - 1}e}")
            from decimal import Decimal, ROUND_HALF_UP
            d = Decimal(repr(fx)) if isinstance(x, float) else Decimal(x.numerator) / Decimal(x.denominator)
            q = d.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
            return Fraction(q) if isinstance(x, Fraction) else float(q)
        # ---- combinatorics / integer functions ---------------------------------
        if name == "fact":
            need(1)
            return self._fact(v[0])
        if name in ("ncr", "npr"):
            need(2)
            a, b = self._int(v[0], 0), self._int(v[1], 0)
            if b > a:
                raise MathErr("Math ERROR")
            return check_range(Fraction(math.comb(a, b) if name == "ncr" else math.perm(a, b)))
        if name in ("gcd", "lcm"):
            if n < 2:
                raise SyntaxErr("Syntax ERROR")
            ints = [abs(self._int(x)) for x in v]
            f = math.gcd if name == "gcd" else math.lcm
            return Fraction(reduce(f, ints))
        if name in ("mod", "quot", "rem"):
            need(2)
            a, b = self._real(v[0]), self._real(v[1])
            if r_cmp(b, ZERO) == 0:
                raise MathErr("Math ERROR")
            if name == "mod":
                q = math.floor(fl(r_div(a, b))) if not (isinstance(a, Fraction) and isinstance(b, Fraction)) else math.floor(a / b)
                return sub(a, mul(b, Fraction(q)))
            q = math.trunc(fl(r_div(a, b))) if not (isinstance(a, Fraction) and isinstance(b, Fraction)) else math.trunc(a / b)
            return Fraction(q) if name == "quot" else sub(a, mul(b, Fraction(q)))
        if name in ("prime", "factor"):
            need(1)
            return v[0]
        # ---- statistics helpers ------------------------------------------------
        if name in ("min", "max", "avg", "mean", "sum", "count"):
            xs = self._flat(v)
            if not xs:
                raise MathErr("Math ERROR")
            if name == "count":
                return Fraction(len(xs))
            if name == "min":
                return reduce(lambda a, b: a if r_cmp(a, b) <= 0 else b, xs)
            if name == "max":
                return reduce(lambda a, b: a if r_cmp(a, b) >= 0 else b, xs)
            s = reduce(add, xs, ZERO)
            return s if name == "sum" else div(s, Fraction(len(xs)))
        if name == "clamp":
            need(3)
            x, lo, hi = v
            return lo if r_cmp(x, lo) < 0 else hi if r_cmp(x, hi) > 0 else x
        if name in ("degrees", "radians"):
            need(1)
            x = fl(self._real(v[0]))
            return math.degrees(x) if name == "degrees" else math.radians(x)
        # ---- random ----------------------------------------------------------
        if name in ("randint", "ranint"):
            need(2)
            a, b = self._int(v[0]), self._int(v[1])
            if a > b:
                raise MathErr("Math ERROR")
            return Fraction(random.randint(a, b))
        if name in ("rand", "random"):
            return random.random()
        # ---- coordinates -------------------------------------------------------
        if name == "pol":
            need(2)
            x, y = self._real(v[0]), self._real(v[1])
            r = r_sqrt(r_add(r_mul(x, x), r_mul(y, y)))
            th = num.atan2_unit(y, x, u)
            self.vars["X"], self.vars["Y"] = r, th
            return PairVal(("r", "θ"), (r, th))
        if name == "rec":
            need(2)
            r, th = self._real(v[0]), self._real(v[1])
            x, y = mul(r, num.trig("cos", th, u)), mul(r, num.trig("sin", th, u))
            self.vars["X"], self.vars["Y"] = x, y
            return PairVal(("x", "y"), (x, y))
        # ---- complex -----------------------------------------------------------
        if name in ("re", "im", "conjg", "conj", "arg"):
            need(1)
            re, im = cparts(v[0])
            if name == "re":
                return re
            if name == "im":
                return im
            if name in ("conjg", "conj"):
                return cnorm(re, r_neg(im))
            return num.atan2_unit(im, re, u)
        # ---- matrices ----------------------------------------------------------
        if name == "det":
            need(1)
            return mat_det(self._mat(v[0]))
        if name == "trn":
            need(1)
            return mat_trn(self._mat(v[0]))
        if name == "inv":
            need(1)
            if isinstance(v[0], Matrix):
                return mat_inv(v[0])
            return div(ONE, v[0])
        if name == "ide":
            need(1)
            return mat_identity(self._int(v[0], 1, 4))
        if name == "rref":
            need(1)
            return mat_rref(self._mat(v[0]))
        if name == "dot":
            need(2)
            return vec_dot(self._vec(v[0]), self._vec(v[1]))
        if name == "cross":
            need(2)
            return vec_cross(self._vec(v[0]), self._vec(v[1]))
        if name == "unitv":
            need(1)
            a = self._vec(v[0])
            nrm = vec_norm(a)
            return Vec([div(x, nrm) for x in a.v])
        if name == "angle":
            need(2)
            a, b = self._vec(v[0]), self._vec(v[1])
            c = div(vec_dot(a, b), mul(vec_norm(a), vec_norm(b)))
            return num.inv_trig("acos", c, u)
        if name == "dms":
            need(1)
            return DMSVal(v[0])
        if name in ("cell", "rng") and self.sheet_cb:
            return self.sheet_cb(name, v)
        raise SyntaxErr(f"Syntax ERROR: {name}")

    # ------------------------------------------------------------------
    def _mat(self, x):
        if not isinstance(x, Matrix):
            raise MathErr("Math ERROR")
        return x

    def _vec(self, x):
        if not isinstance(x, Vec):
            raise MathErr("Math ERROR")
        return x

    def _sqrt(self, x):
        if isinstance(x, CNum):
            import cmath
            return c_from_py(cmath.sqrt(x.to_py()))
        x = self._real(x)
        if r_cmp(x, ZERO) < 0:
            if not self.complex_mode:
                raise MathErr("Math ERROR")
            return cnorm(ZERO, r_sqrt(r_neg(x)))
        return r_sqrt(x)

    def _ln(self, x):
        if isinstance(x, CNum):
            import cmath
            return c_from_py(cmath.log(x.to_py()))
        x = self._real(x)
        f = fl(x)
        if f == 0:
            raise MathErr("Math ERROR")
        if f < 0:
            if not self.complex_mode:
                raise MathErr("Math ERROR")
            return cnorm(math.log(-f), math.pi)
        if isinstance(x, Fraction) and x == 1:
            return ZERO
        if isinstance(x, float):
            n = round(math.log(f))
            if n != 0 and abs(f - math.e ** n) < 1e-13 * f:
                return Fraction(n)
        return math.log(f)

    def _log(self, base, x):
        base = self._real(base)
        if isinstance(x, CNum):
            import cmath
            return c_from_py(cmath.log(x.to_py()) / math.log(fl(base)))
        x = self._real(x)
        if fl(x) <= 0 or fl(base) <= 0 or fl(base) == 1:
            raise MathErr("Math ERROR")
        if isinstance(x, Fraction) and isinstance(base, Fraction):
            if x == 1:
                return ZERO
            for k in range(-60, 61):
                if k and base ** k == x:
                    return Fraction(k)
        return math.log(fl(x)) / math.log(fl(base))

    # ------------------------------------------------------------------
    # CALC / SOLVE
    # ------------------------------------------------------------------
    def needed_vars(self, text):
        ast = parse(text, allow_assign=False)
        return sorted(free_vars(ast))

    def calc_with(self, text, values: dict):
        ast = parse(text, allow_assign=False)
        env = {k: v for k, v in values.items()}
        return self.eval_ast(ast, env)

    def solve(self, text: str, var: str = "x", guess=0.0):
        """solve  lhs = rhs  (or expr = 0) for `var`; returns (root, left-right residual)"""
        ast = parse(text, allow_assign=False)
        if ast[0] == "cmp" and ast[1] == "=":
            lhs, rhs = ast[2], ast[3]
        else:
            lhs, rhs = ast, ("num", ZERO)
        others = {k: v for k, v in self.vars.items()}

        def f(x):
            e = dict(others)
            e[var] = x
            return fl(self.eval_ast(lhs, e)) - fl(self.eval_ast(rhs, e))

        root = num.find_root(f, float(guess))
        return num.tidy(root), f(root)
