"""
Tree model of a "natural display" expression.

A Seq is a list of Nodes.  A Node is either a plain token ('tok': a digit, an operator, a
function name such as "sin(" ...) or a structure with child Seqs ("slots"): fractions,
roots, superscripts, integrals ...  The very same tree is used for the editable input and for
the read-only results, and can be serialised to a plain string for the parser.
"""
from __future__ import annotations

SLOT_COUNT = {
    "tok": 0, "frac": 2, "sqrt": 1, "root": 2, "sup": 1, "logb": 2, "abs": 1,
    "sigma": 3, "prod": 3, "integ": 3, "deriv": 2, "mixed": 3,
}
# vertical navigation: kind -> {slot: (up_slot, down_slot)}
VERTICAL = {
    "frac": {0: (None, 1), 1: (0, None)},
    "root": {0: (None, 1), 1: (0, None)},
    "mixed": {1: (None, 2), 2: (1, None)},
    "sigma": {0: (2, 1), 1: (2, None), 2: (None, 1)},
    "prod": {0: (2, 1), 1: (2, None), 2: (None, 1)},
    "integ": {0: (2, 1), 1: (2, None), 2: (None, 1)},
}
SER_TOK = {"×": "*", "÷": "/", "−": "-", "ᴇ": "@", "and": " and ", "or": " or ", "xor": " xor ",
           "xnor": " xnor ", "Not(": "not(", "Neg(": "neg("}


class Seq:
    __slots__ = ("items", "owner", "slot")

    def __init__(self, owner=None, slot=0):
        self.items: list[Node] = []
        self.owner: Node | None = owner
        self.slot = slot

    def add(self, node):
        node.parent = self
        self.items.append(node)
        return node

    def is_empty(self):
        return not self.items


class Node:
    __slots__ = ("kind", "text", "slots", "parent")

    def __init__(self, kind="tok", text="", nslots=None):
        self.kind = kind
        self.text = text
        n = SLOT_COUNT.get(kind, 0) if nslots is None else nslots
        self.slots = [Seq(self, i) for i in range(n)]
        self.parent: Seq | None = None


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------
def tok(text) -> Node:
    return Node("tok", text)


def seq_from(*parts) -> Seq:
    """seq_from("1", "+", node, seq ...) – strings become tokens, Seqs are spliced"""
    s = Seq()
    for p in parts:
        if isinstance(p, str):
            s.add(tok(p))
        elif isinstance(p, Seq):
            for it in list(p.items):
                s.add(it)
        elif isinstance(p, Node):
            s.add(p)
        else:
            raise TypeError(p)
    return s


def structure(kind, *slot_seqs, text="") -> Node:
    n = Node(kind, text, nslots=len(slot_seqs))
    for i, sq in enumerate(slot_seqs):
        for it in list(sq.items):
            n.slots[i].add(it)
    return n


def frac_node(num: Seq, den: Seq) -> Node:
    return structure("frac", num, den)


def sqrt_node(rad: Seq) -> Node:
    return structure("sqrt", rad)


def sup_node(exp: Seq) -> Node:
    return structure("sup", exp)


def matrix_node(rows: int, cols: int, cells: list[Seq]) -> Node:
    return structure("matrix", *cells, text=f"{rows}x{cols}")


def clone(seq: Seq) -> Seq:
    return json_to_seq(seq_to_json(seq))


# ---------------------------------------------------------------------------
# serialisation
# ---------------------------------------------------------------------------
def serialize(seq: Seq) -> str:
    out = []
    for it in seq.items:
        k = it.kind
        s = [serialize(x) for x in it.slots]
        if k == "tok":
            out.append(SER_TOK.get(it.text, it.text))
        elif k == "frac":
            out.append(f"(({s[0]})/({s[1]}))")
        elif k == "sqrt":
            out.append(f"sqrt({s[0]})")
        elif k == "root":
            out.append(f"root({s[0]},{s[1]})")
        elif k == "sup":
            out.append(f"^({s[0]})")
        elif k == "logb":
            out.append(f"logb({s[0]},{s[1]})")
        elif k == "abs":
            out.append(f"abs({s[0]})")
        elif k in ("sigma", "prod"):
            out.append(f"{k}({s[0]},x,{s[1]},{s[2]})")
        elif k == "integ":
            out.append(f"integ({s[0]},{s[1]},{s[2]})")
        elif k == "deriv":
            out.append(f"deriv({s[0]},{s[1]})")
        elif k == "mixed":
            out.append(f"(({s[0]})+({s[1]})/({s[2]}))")
        else:
            out.append("")
    return "".join(out)


def _simple(t: str) -> bool:
    import re
    return bool(re.fullmatch(r"[A-Za-z0-9.π]+", t))


def to_plain(seq: Seq) -> str:
    """human readable text (for copy / clipboard)"""
    out = []
    for it in seq.items:
        k = it.kind
        s = [to_plain(x) for x in it.slots]
        if k == "tok":
            out.append(it.text)
        elif k == "frac":
            out.append(f"{s[0] if _simple(s[0]) else '(' + s[0] + ')'}/{s[1] if _simple(s[1]) else '(' + s[1] + ')'}")
        elif k == "sqrt":
            out.append(f"√{s[0]}" if _simple(s[0]) else f"√({s[0]})")
        elif k == "root":
            out.append(f"root({s[0]},{s[1]})")
        elif k == "sup":
            out.append(f"^{s[0]}" if _simple(s[0]) else f"^({s[0]})")
        elif k == "logb":
            out.append(f"log_{s[0]}({s[1]})")
        elif k == "abs":
            out.append(f"|{s[0]}|")
        elif k in ("sigma", "prod"):
            out.append(f"{'Σ' if k == 'sigma' else 'Π'}(x={s[1]}..{s[2]}, {s[0]})")
        elif k == "integ":
            out.append(f"∫({s[0]}, {s[1]}..{s[2]})dx")
        elif k == "deriv":
            out.append(f"d/dx({s[0]})|x={s[1]}")
        elif k == "mixed":
            out.append(f"{s[0]} {s[1]}/{s[2]}")
        elif k == "matrix":
            r, c = map(int, it.text.split("x"))
            rows = [" ".join(s[i * c:(i + 1) * c]) for i in range(r)]
            out.append("[" + "; ".join(rows) + "]")
    return "".join(out)


def seq_to_json(seq: Seq):
    out = []
    for it in seq.items:
        if it.kind == "tok":
            out.append(it.text)
        else:
            out.append({"k": it.kind, "t": it.text, "s": [seq_to_json(x) for x in it.slots]})
    return out


def json_to_seq(data, owner=None, slot=0) -> Seq:
    s = Seq(owner, slot)
    for it in data:
        if isinstance(it, str):
            s.add(tok(it))
        else:
            n = Node(it["k"], it.get("t", ""), nslots=len(it["s"]))
            for i, sub in enumerate(it["s"]):
                n.slots[i] = json_to_seq(sub, n, i)
            s.add(n)
    return s
