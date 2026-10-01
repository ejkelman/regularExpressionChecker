"""
Decide whether a regular expression over {0, 1} is unambiguous.

Allowed characters: '0', '1', '*', '(', ')'.  Concatenation is implicit.
Grammar:
    expr := term*            (empty expr = epsilon, so "()" and "" are epsilon)
    term := atom '*'*
    atom := '0' | '1' | '(' expr ')'

"Unambiguous" means every word in the language has exactly one parse tree.
Empty iterations count as distinct parses, so a star over a nullable
expression, e.g. (0*)* or ()*, is ambiguous (epsilon has infinitely many parses).

Usage:
    python regex_ambiguity.py "(01)*"        -> True
    python regex_ambiguity.py "0*0*"         -> False  (+ a witness word)
"""
from collections import deque
import sys

# ---------------------------------------------------------------- parsing
# AST nodes: ("eps",) | ("sym", c) | ("cat", a, b) | ("star", a)

def parse(s):
    pos = 0

    def peek():
        return s[pos] if pos < len(s) else None

    def expr():
        nonlocal pos
        node = None
        while peek() is not None and peek() != ")":
            t = term()
            node = t if node is None else ("cat", node, t)
        return node if node is not None else ("eps",)

    def term():
        nonlocal pos
        node = atom()
        while peek() == "*":
            pos += 1
            node = ("star", node)
        return node

    def atom():
        nonlocal pos
        c = peek()
        if c in ("0", "1"):
            pos += 1
            return ("sym", c)
        if c == "(":
            pos += 1
            node = expr()
            if peek() != ")":
                raise ValueError(f"missing ')' (position {pos})")
            pos += 1
            return node
        if c == "*":
            raise ValueError(f"'*' has nothing to repeat (position {pos})")
        raise ValueError(f"unexpected character {c!r} (position {pos})")

    for i, ch in enumerate(s):
        if ch not in "01*()":
            raise ValueError(f"illegal character {ch!r} (position {i})")
    node = expr()
    if pos != len(s):
        raise ValueError(f"unmatched ')' (position {pos})")
    return node


# ------------------------------------------- step 1: epsilon-ambiguity check
def eps_ambiguous(node):
    """True if some subexpression matches the empty word in 2+ ways."""
    def count(n):  # number of ways n matches epsilon, capped at 2
        kind = n[0]
        if kind == "eps":
            return 1
        if kind == "sym":
            return 0
        if kind == "cat":
            a, b = count(n[1]), count(n[2])
            return min(2, a * b)
        if kind == "star":
            return 1 if count(n[1]) == 0 else 2
    # count() recurses everywhere, but a capped 2 deep inside propagates up
    # only through cat/star, so just check the root plus every star body.
    def walk(n):
        if n[0] == "star" and count(n[1]) >= 1:
            return True
        return any(walk(c) for c in n[1:] if isinstance(c, tuple))
    return count(node) >= 2 or walk(node)


# ------------------------------------------------ step 2: Glushkov automaton
def glushkov(root):
    """Return (delta, finals).  State 0 = start, states 1..n = symbol positions.
    delta[state][symbol] = set of next states."""
    symbols = [None]          # symbols[i] = character at position i
    follow = {}

    def build(n):             # returns (nullable, first, last)
        kind = n[0]
        if kind == "eps":
            return True, set(), set()
        if kind == "sym":
            symbols.append(n[1])
            i = len(symbols) - 1
            follow[i] = set()
            return False, {i}, {i}
        if kind == "cat":
            na, fa, la = build(n[1])
            nb, fb, lb = build(n[2])
            for p in la:
                follow[p] |= fb
            first = fa | (fb if na else set())
            last = lb | (la if nb else set())
            return na and nb, first, last
        if kind == "star":
            _, f, l = build(n[1])
            for p in l:
                follow[p] |= f
            return True, f, l

    nullable, first, last = build(root)
    delta = {0: {}}
    for i in range(1, len(symbols)):
        delta[i] = {}
    for q in first:
        delta[0].setdefault(symbols[q], set()).add(q)
    for p, qs in follow.items():
        for q in qs:
            delta[p].setdefault(symbols[q], set()).add(q)
    finals = set(last) | ({0} if nullable else set())
    return delta, finals


# ------------------------------------------- step 3: product automaton check
def _bfs(starts, succ):
    """Generic BFS. succ(state) yields (label, next). Returns parent map."""
    parent = {s: None for s in starts}
    dq = deque(starts)
    while dq:
        u = dq.popleft()
        for lab, v in succ(u):
            if v not in parent:
                parent[v] = (u, lab)
                dq.append(v)
    return parent


def _path(parent, target):
    word = []
    while parent[target] is not None:
        target, lab = parent[target]
        word.append(lab)
    return "".join(reversed(word))


def find_ambiguity(regex):
    """Return None if unambiguous, else a word with 2+ parses
    (the word "" for epsilon-ambiguity)."""
    root = parse(regex)
    if eps_ambiguous(root):
        return ""
    delta, finals = glushkov(root)

    def fwd(pq):
        p, q = pq
        for a, ps in delta[p].items():
            if a in delta[q]:
                for p2 in ps:
                    for q2 in delta[q][a]:
                        yield a, (p2, q2)

    reach = _bfs([(0, 0)], fwd)

    # reverse edges restricted to reachable pairs -> co-reachability
    rev = {s: [] for s in reach}
    for s in reach:
        for _, t in fwd(s):
            rev[t].append(s)
    good_finals = [s for s in reach if s[0] in finals and s[1] in finals]
    coreach = _bfs(good_finals, lambda s: (("", u) for u in rev[s]))

    for (p, q) in reach:
        if p != q and (p, q) in coreach:
            prefix = _path(reach, (p, q))
            # shortest suffix from (p,q) to an accepting pair
            tail_parent = _bfs([(p, q)], fwd)
            end = next(s for s in tail_parent
                       if s[0] in finals and s[1] in finals)
            return prefix + _path(tail_parent, end)
    return None


def is_unambiguous(regex):
    return find_ambiguity(regex) is None


# ------------------------------------------- optional: one-unambiguity check
def is_one_unambiguous(regex):
    """Stricter, deterministic-matching notion: one symbol of lookahead always
    identifies the position.  (E.g. 0*0 is unambiguous but NOT one-unambiguous.)"""
    root = parse(regex)
    if eps_ambiguous(root):
        return False
    delta, _ = glushkov(root)
    return all(len(targets) == 1 for st in delta.values()
               for targets in st.values())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    try:
        w = find_ambiguity(sys.argv[1])
    except ValueError as e:
        print(f"Parse error: {e}")
        sys.exit(2)
    if w is None:
        print("True")
    else:
        print(f"False  (ambiguous word: {w!r})" if w else
              "False  (empty word has multiple parses)")
