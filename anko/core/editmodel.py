"""Editing model for the natural-input line: cursor, templates, navigation, undo."""
from __future__ import annotations

from .mathtree import (Seq, Node, tok, VERTICAL, SLOT_COUNT, serialize, seq_to_json, json_to_seq, to_plain)
from .parser import FUNC_NAMES

AUTO_EXIT = set("+−×÷=<>≤≥≠,→")
TOKEN_CHARS_FOR_OPERAND = set("0123456789.!%°′″")
OPERAND_TEXT = {"π", "Ans", "PreAns", "e", "i", "x", "X", "Y", "M", "A", "B", "C", "D", "E", "F", "Ran#",
                "MatAns", "VctAns", "ᴇ"}
MERGE_FUNCS = sorted((f for f in FUNC_NAMES if f not in ("sigma", "prod", "integ", "deriv", "sqrt", "abs",
                                                          "logb", "root", "cell", "rng")), key=len, reverse=True)


def index_of(node: Node) -> int:
    for i, n in enumerate(node.parent.items):
        if n is node:
            return i
    raise ValueError


class EditModel:
    def __init__(self):
        self.root = Seq()
        self.seq = self.root
        self.pos = 0
        self.undo_stack = []
        self.redo_stack = []

    # -- state ---------------------------------------------------------------
    @property
    def cursor(self):
        return (self.seq, self.pos)

    def is_empty(self):
        return not self.root.items

    def text(self):
        return serialize(self.root)

    def plain(self):
        return to_plain(self.root)

    def _path(self):
        path, s = [], self.seq
        while s.owner is not None:
            path.append((index_of(s.owner), s.slot))
            s = s.owner.parent
        path.reverse()
        return path

    def snapshot(self):
        return (seq_to_json(self.root), self._path(), self.pos)

    def restore(self, snap):
        data, path, pos = snap
        self.root = json_to_seq(data)
        s = self.root
        for i, slot in path:
            s = s.items[i].slots[slot]
        self.seq, self.pos = s, min(pos, len(s.items))

    def _push(self):
        self.undo_stack.append(self.snapshot())
        if len(self.undo_stack) > 150:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.snapshot())
            self.restore(self.undo_stack.pop())
            return True
        return False

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.snapshot())
            self.restore(self.redo_stack.pop())
            return True
        return False

    def clear(self):
        if self.root.items:
            self._push()
        self.root = Seq()
        self.seq, self.pos = self.root, 0

    def load(self, seq: Seq, push=True):
        if push:
            self._push()
        self.root = json_to_seq(seq_to_json(seq))
        self.seq, self.pos = self.root, len(self.root.items)

    # -- insertion -----------------------------------------------------------------
    def _insert_node(self, node: Node):
        node.parent = self.seq
        self.seq.items.insert(self.pos, node)
        self.pos += 1

    def insert_tok(self, text: str):
        self._push()
        if text == ")":
            # a ')' typed inside a fraction/root/exponent that has no open bracket of its own
            # closes that structure; it is only inserted if an outer '(' is waiting for it
            exited = False
            while self.seq.owner is not None and self._unmatched_open(self.seq, self.pos) == 0:
                self.seq, self.pos = self.seq.owner.parent, index_of(self.seq.owner) + 1
                exited = True
            if exited and self._unmatched_open(self.seq, self.pos) == 0:
                return
        elif text in AUTO_EXIT:
            # keyboard-typed fractions / exponents end at the next operator
            while (self.seq.owner is not None and self.seq.owner.text == "auto" and self.seq.items
                   and self.seq.slot == len(self.seq.owner.slots) - 1
                   and self._unmatched_open(self.seq, self.pos) == 0):
                self.seq, self.pos = self.seq.owner.parent, index_of(self.seq.owner) + 1
        items, pos = self.seq.items, self.pos
        if text == "(":
            # merge typed letters into a function token:  s i n (  ->  "sin("
            j = pos
            while j > 0 and items[j - 1].kind == "tok" and len(items[j - 1].text) == 1 and items[j - 1].text.isalpha():
                j -= 1
            letters = "".join(n.text for n in items[j:pos]).lower()
            for name in ["sqrt", "abs"] + MERGE_FUNCS:
                if letters.endswith(name):
                    start = pos - len(name)
                    del items[start:pos]
                    self.pos = start
                    if name == "sqrt":
                        return self._template("sqrt", push=False)
                    if name == "abs":
                        return self._template("abs", push=False)
                    text = name[0].upper() + name[1:] + "(" if name in ("pol", "rec", "det", "trn", "dot", "cross", "unitv", "rref", "ide", "norm", "angle") else name + "("
                    if name in ("rnd",):
                        text = "Rnd("
                    break
        elif text == "i" and pos > 0 and items[pos - 1].kind == "tok" and items[pos - 1].text == "p":
            del items[pos - 1]
            self.pos -= 1
            text = "π"
        node = tok(text)
        self._insert_node(node)

    @staticmethod
    def _unmatched_open(seq, pos):
        depth = 0
        for n in seq.items[:pos]:
            if n.kind == "tok":
                if n.text.endswith("("):
                    depth += 1
                elif n.text == ")":
                    depth = max(0, depth - 1) if depth else 0
        return depth

    def insert_text(self, s: str):
        for ch in s:
            if ch in "*":
                ch = "×"
            elif ch == "-":
                ch = "−"
            if ch == "/":
                self.template("frac", wrap=True, auto=True)
            elif ch == "^":
                self.template("sup", auto=True)
            elif ch == "√":
                self.template("sqrt")
            elif ch.isspace():
                continue
            else:
                self.insert_tok(ch)

    def _operand_start(self):
        """index in current seq where the operand before the cursor starts (or pos if none)"""
        items, pos = self.seq.items, self.pos
        j = pos
        if j == 0:
            return pos
        last = items[j - 1]
        if last.kind == "tok" and last.text == ")":
            depth = 0
            k = j - 1
            while k >= 0:
                n = items[k]
                if n.kind == "tok" and n.text == ")":
                    depth += 1
                elif n.kind == "tok" and (n.text == "(" or n.text.endswith("(")):
                    depth -= 1
                    if depth == 0:
                        return k
                k -= 1
            return pos
        while j > 0:
            n = items[j - 1]
            if n.kind == "tok" and (n.text in TOKEN_CHARS_FOR_OPERAND or n.text in OPERAND_TEXT):
                j -= 1
            elif n.kind in ("sup", "sqrt", "root", "abs", "frac", "mixed") and j > 0:
                j -= 1
            else:
                break
        return j

    def template(self, kind: str, wrap=False, auto=False):
        self._push()
        self._template(kind, wrap, auto=auto)

    def _template(self, kind: str, wrap=False, push=False, auto=False):
        node = Node(kind)
        if auto:
            node.text = "auto"
        target = 0
        if kind == "frac" and wrap:
            start = self._operand_start()
            moved = self.seq.items[start:self.pos]
            if moved:
                if (len(moved) >= 2 and moved[0].kind == "tok" and moved[0].text == "(" and moved[-1].text == ")"
                        and moved[-1].kind == "tok"):
                    moved = moved[1:-1]
                del self.seq.items[start:self.pos]
                self.pos = start
                for m in moved:
                    node.slots[0].add(m)
                target = 1
        self._insert_node(node)
        if node.slots:
            self.seq, self.pos = node.slots[target], 0

    def insert_seq(self, seq: Seq):
        from .mathtree import clone
        self._push()
        for n in list(clone(seq).items):
            self._insert_node(n)

    # -- deletion ----------------------------------------------------------------
    def backspace(self):
        seq, pos = self.seq, self.pos
        if pos > 0:
            n = seq.items[pos - 1]
            if n.kind == "tok":
                self._push()
                del seq.items[pos - 1]
                self.pos -= 1
            elif all(not s.items for s in n.slots):
                self._push()
                del seq.items[pos - 1]
                self.pos -= 1
            else:
                last = n.slots[-1]
                self.seq, self.pos = last, len(last.items)
            return
        owner = seq.owner
        if owner is None:
            return
        if all(not s.items for s in owner.slots):
            self._push()
            parent = owner.parent
            i = index_of(owner)
            del parent.items[i]
            self.seq, self.pos = parent, i
        else:
            self.move_left()

    def delete_forward(self):
        if self.pos < len(self.seq.items):
            n = self.seq.items[self.pos]
            if n.kind == "tok" or all(not s.items for s in n.slots):
                self._push()
                del self.seq.items[self.pos]

    # -- navigation --------------------------------------------------------------------
    def move_left(self):
        seq, pos = self.seq, self.pos
        if pos > 0:
            n = seq.items[pos - 1]
            if n.slots:
                self.seq, self.pos = n.slots[-1], len(n.slots[-1].items)
            else:
                self.pos -= 1
            return True
        owner = seq.owner
        if owner is None:
            return False
        if seq.slot > 0:
            prev = owner.slots[seq.slot - 1]
            self.seq, self.pos = prev, len(prev.items)
        else:
            self.seq, self.pos = owner.parent, index_of(owner)
        return True

    def move_right(self):
        seq, pos = self.seq, self.pos
        if pos < len(seq.items):
            n = seq.items[pos]
            if n.slots:
                self.seq, self.pos = n.slots[0], 0
            else:
                self.pos += 1
            return True
        owner = seq.owner
        if owner is None:
            return False
        if seq.slot < len(owner.slots) - 1:
            self.seq, self.pos = owner.slots[seq.slot + 1], 0
        else:
            self.seq, self.pos = owner.parent, index_of(owner) + 1
        return True

    def move_vertical(self, up: bool):
        seq, pos = self.seq, self.pos
        while seq.owner is not None:
            owner = seq.owner
            tbl = VERTICAL.get(owner.kind, {})
            if seq.slot in tbl:
                t = tbl[seq.slot][0 if up else 1]
                if t is not None:
                    tgt = owner.slots[t]
                    self.seq, self.pos = tgt, min(pos, len(tgt.items))
                    return True
            if owner.kind == "sup" and not up:
                self.seq, self.pos = owner.parent, index_of(owner) + 1
                return True
            pos = index_of(owner)
            seq = owner.parent
        return False

    def home(self):
        self.seq, self.pos = self.root, 0

    def end(self):
        self.seq, self.pos = self.root, len(self.root.items)

    def set_cursor(self, seq: Seq, pos: int):
        self.seq, self.pos = seq, max(0, min(pos, len(seq.items)))
