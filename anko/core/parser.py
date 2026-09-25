"""
Tokeniser + parser producing a small tuple-based AST.

AST nodes
  ('num', value)              ('var', name)          ('const', name)
  ('neg', x)                  ('bin', op, l, r)      ('cmp', op, l, r)
  ('call', name, [args])      ('fact', x)            ('pct', x)
  ('deg', x)                  ('dms', d, m, s)       ('polar', r, theta)
  ('sto', expr, varname)
"""
from __future__ import annotations

import re
from fractions import Fraction

from .values import SyntaxErr

FUNC_NAMES = {
    "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
    "log", "ln", "logb", "exp", "abs", "sqrt", "cbrt", "root", "floor", "ceil", "int", "frac",
    "round", "rnd", "sign", "ncr", "npr", "fact", "gcd", "lcm", "mod", "min", "max", "avg", "mean",
    "sum", "clamp", "pow", "log2", "log10", "randint", "ranint", "rand", "random", "pol", "rec",
    "re", "im", "arg", "conjg", "conj", "det", "trn", "inv", "ide", "dot", "cross", "angle",
    "unitv", "norm", "rref", "sigma", "prod", "integ", "deriv", "dms", "degrees", "radians",
    "cell", "rng", "count", "hyp", "quot", "rem", "prime", "factor",
}
MULTI_NAMES = {"ans", "preans", "matans", "vctans", "mata", "matb", "matc", "matd",
               "vcta", "vctb", "vctc", "vctd", "pi", "ran#"} | FUNC_NAMES
VARIABLES = set("ABCDEFXYM")
CONST_NAMES = {"ans", "preans", "matans", "vctans", "mata", "matb", "matc", "matd",
               "vcta", "vctb", "vctc", "vctd", "pi", "ran#"}
BASE_WORDS = {"and", "or", "xor", "xnor", "not", "neg"}

_num_re = re.compile(r"(\d+\.?\d*|\.\d+)")
_id_re = re.compile(r"[A-Za-zπθ#_]+")
_SINGLE_OPS = "+-*/^!%°'\"(),=<>≤≥≠∠→"
_LONGEST_FIRST = sorted(MULTI_NAMES, key=len, reverse=True)


def _split_ident(run: str):
    out = []
    i = 0
    low = run.lower()
    while i < len(run):
        ch = run[i]
        if ch == "π":
            out.append(("const", "pi"))
            i += 1
            continue
        if ch == "θ":
            out.append(("var", "theta"))
            i += 1
            continue
        hit = None
        for n in _LONGEST_FIRST:
            if low.startswith(n, i):
                hit = n
                break
        if hit:
            if hit in CONST_NAMES:
                out.append(("const", hit))
            else:
                out.append(("name", hit))
            i += len(hit)
            continue
        if ch == "e":
            out.append(("const", "e"))
        elif ch == "i":
            out.append(("const", "i"))
        elif ch == "x":
            out.append(("var", "x"))
        elif ch.upper() in VARIABLES:
            out.append(("var", ch.upper()))
        else:
            raise SyntaxErr(f"Syntax ERROR: unknown symbol '{ch}'")
        i += 1
    return out


def tokenize(text: str):
    text = (text.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
            .replace("’", "'").replace("″", '"').replace("′", "'").replace("ᴇ", "@")
            .replace("≦", "≤").replace("≧", "≥").replace("⁻¹", "^(-1)").replace("²", "^(2)")
            .replace("³", "^(3)").replace("√", "sqrt").replace("⇒", "→").replace("ˣ", ""))
    toks = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        m = _num_re.match(text, i)
        if m:
            s = m.group(1)
            i = m.end()
            val = float(s) if "." in s else Fraction(int(s))
            if i < n and text[i] == "@":
                j = i + 1
                sign = 1
                if j < n and text[j] in "+-":
                    sign = -1 if text[j] == "-" else 1
                    j += 1
                k = j
                while k < n and text[k].isdigit():
                    k += 1
                if k == j:
                    raise SyntaxErr("Syntax ERROR")
                e = sign * int(text[j:k])
                if abs(e) > 400:
                    raise SyntaxErr("Math ERROR")
                val = val * 10.0 ** e if isinstance(val, float) else val * Fraction(10) ** e
                i = k
            toks.append(("num", val))
            continue
        m = _id_re.match(text, i)
        if m:
            toks.extend(_split_ident(m.group(0)))
            i = m.end()
            continue
        if c == "(":
            toks.append(("lp", c))
        elif c == ")":
            toks.append(("rp", c))
        elif c == ",":
            toks.append(("comma", c))
        elif c in _SINGLE_OPS:
            toks.append(("op", c))
        else:
            raise SyntaxErr(f"Syntax ERROR: unexpected '{c}'")
        i += 1
    toks.append(("eof", ""))
    return toks


def tokenize_base(text: str, base: int):
    """Base-N tokenizer: numbers are integers written in `base`."""
    text = text.replace("×", "*").replace("÷", "/").replace("−", "-")
    toks = []
    i, n = 0, len(text)
    digits = "0123456789ABCDEF"[:base]
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c.isalnum():
            j = i
            while j < n and text[j].isalnum():
                j += 1
            run = text[i:j]
            k = 0
            digs = ""
            while k < len(run):
                low = run[k:].lower()
                word = next((w for w in ("xnor", "and", "xor", "not", "neg", "or") if low.startswith(w)), None)
                if word and (word != "and" or digs == "" or True):
                    if digs:
                        toks.append(("num", Fraction(int(digs, base))))
                        digs = ""
                    toks.append(("name", word))
                    k += len(word)
                    continue
                if run[k].upper() not in digits:
                    raise SyntaxErr("Syntax ERROR")
                digs += run[k]
                k += 1
            if digs:
                toks.append(("num", Fraction(int(digs, base))))
            i = j
            continue
        if c == "(":
            toks.append(("lp", c))
        elif c == ")":
            toks.append(("rp", c))
        elif c == ",":
            toks.append(("comma", c))
        elif c in "+-*/":
            toks.append(("op", c))
        else:
            raise SyntaxErr("Syntax ERROR")
        i += 1
    toks.append(("eof", ""))
    return toks


class Parser:
    def __init__(self, toks, base_mode=False, allow_assign=True):
        self.t = toks
        self.i = 0
        self.base = base_mode
        self.allow_assign = allow_assign

    # helpers
    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def at_op(self, *ops):
        t = self.peek()
        return t[0] == "op" and t[1] in ops

    def next(self):
        t = self.t[self.i]
        self.i += 1
        return t

    # grammar
    def parse(self):
        if self.peek()[0] == "eof":
            raise SyntaxErr("Syntax ERROR")
        node = self.statement()
        if self.peek()[0] != "eof":
            raise SyntaxErr("Syntax ERROR")
        return node

    def statement(self):
        if (self.allow_assign and self.peek()[0] == "var" and self.peek()[1] != "x"
                and self.peek(1) == ("op", "=")):
            var = self.next()[1]
            self.next()
            rhs = self.compare()
            return ("sto", rhs, var)
        node = self.compare()
        while self.at_op("→"):
            self.next()
            t = self.next()
            if t[0] != "var" and not (t[0] == "const" and t[1] in ("mata", "matb", "matc", "matd", "vcta", "vctb", "vctc", "vctd")):
                raise SyntaxErr("Syntax ERROR")
            node = ("sto", node, t[1])
        return node

    def compare(self):
        left = self.add()
        if self.at_op("<", ">", "=", "≤", "≥", "≠"):
            op = self.next()[1]
            right = self.add()
            return ("cmp", op, left, right)
        return left

    def add(self):
        left = self.mul()
        while self.at_op("+", "-"):
            op = self.next()[1]
            left = ("bin", op, left, self.mul())
        return left

    def mul(self):
        left = self.factor()
        while True:
            if self.at_op("*", "/"):
                op = self.next()[1]
                left = ("bin", op, left, self.factor())
            elif self.base and self.peek()[0] == "name" and self.peek()[1] in ("and", "or", "xor", "xnor"):
                op = self.next()[1]
                left = ("bin", op, left, self.factor())
            else:
                return left

    def factor(self):
        if self.at_op("-"):
            self.next()
            return ("neg", self.factor())
        if self.at_op("+"):
            self.next()
            return self.factor()
        return self.permutation()

    def _infix_perm(self):
        t = self.peek()
        return t[0] == "name" and t[1] in ("npr", "ncr") and self.peek(1)[0] != "lp"

    def permutation(self):
        left = self.implicit()
        while self._infix_perm():
            name = self.next()[1]
            left = ("call", name, [left, self.implicit()])
        return left

    def _starts_primary(self):
        k, v = self.peek()
        if k in ("num", "lp", "var", "const"):
            return True
        if k == "name":
            if v in ("npr", "ncr") and self.peek(1)[0] != "lp":
                return False
            return not (self.base and v in ("and", "or", "xor", "xnor"))
        return False

    def implicit(self):
        left = self.power()
        while self._starts_primary():
            left = ("bin", "*", left, self.power())
        if self.at_op("∠"):
            self.next()
            left = ("polar", left, self.power())
        return left

    def power(self):
        base = self.postfix()
        if self.at_op("^"):
            self.next()
            return ("bin", "^", base, self.exponent())
        return base

    def exponent(self):
        if self.at_op("-"):
            self.next()
            return ("neg", self.exponent())
        if self.at_op("+"):
            self.next()
            return self.exponent()
        return self.power()

    def postfix(self):
        node = self.primary()
        while True:
            if self.at_op("!"):
                self.next()
                node = ("fact", node)
            elif self.at_op("%"):
                self.next()
                node = ("pct", node)
            elif self.at_op("°"):
                self.next()
                m = s = None
                if self.peek()[0] == "num" and self.peek(1) == ("op", "'"):
                    m = self.next()[1]
                    self.next()
                if self.peek()[0] == "num" and self.peek(1) == ("op", '"'):
                    s = self.next()[1]
                    self.next()
                node = ("dms", node, m, s) if (m is not None or s is not None) else ("deg", node)
            else:
                return node

    def primary(self):
        k, v = self.next()
        if k == "num":
            return ("num", v)
        if k in ("var", "const"):
            return (k, v)
        if k == "lp":
            node = self.statement_in_paren()
            return node
        if k == "name":
            if v in BASE_WORDS and self.base:
                if self.peek()[0] != "lp":
                    raise SyntaxErr("Syntax ERROR")
            if self.peek()[0] != "lp":
                raise SyntaxErr("Syntax ERROR")
            self.next()
            args = []
            if self.peek()[0] == "rp":
                self.next()
                return ("call", v, args)
            while True:
                args.append(self.compare())
                if self.peek()[0] == "comma":
                    self.next()
                    continue
                break
            self._close()
            return ("call", v, args)
        raise SyntaxErr("Syntax ERROR")

    def statement_in_paren(self):
        node = self.compare()
        self._close()
        return node

    def _close(self):
        if self.peek()[0] == "rp":
            self.next()
        elif self.peek()[0] != "eof":  # a missing ')' at the very end is auto-closed
            raise SyntaxErr("Syntax ERROR")


def parse(text: str, base: int | None = None, allow_assign=True):
    if len(text) > 4000:
        raise SyntaxErr("Syntax ERROR: expression too long")
    if base:
        return Parser(tokenize_base(text, base), base_mode=True, allow_assign=False).parse()
    return Parser(tokenize(text), allow_assign=allow_assign).parse()


def free_vars(ast, acc=None):
    """variables used by an expression (for the CALC key)"""
    acc = set() if acc is None else acc
    if isinstance(ast, tuple):
        if ast and ast[0] == "var":
            acc.add(ast[1])
        for a in ast[1:]:
            if isinstance(a, (tuple, list)):
                if isinstance(a, list):
                    for b in a:
                        free_vars(b, acc)
                else:
                    free_vars(a, acc)
    return acc
