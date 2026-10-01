import itertools
import random
from functools import lru_cache

import pytest

from regex_ambiguity import (
    eps_ambiguous,
    find_ambiguity,
    is_one_unambiguous,
    is_unambiguous,
    parse,
)

# ---------------------------------------------------------------- known cases
UNAMBIGUOUS = ["", "()", "0", "01", "(01)*", "0*1", "0*1*", "(0*1)*0*", "0*0", "(0)*(1)*0"]
AMBIGUOUS = ["0*0*", "(0*)*", "()*", "0**", "(00)*(000)*", "(0*1*)*", "((01)*)*"]


@pytest.mark.parametrize("r", UNAMBIGUOUS)
def test_unambiguous(r):
    assert is_unambiguous(r)


@pytest.mark.parametrize("r", AMBIGUOUS)
def test_ambiguous(r):
    assert not is_unambiguous(r)


def test_one_unambiguity_is_stricter():
    assert is_unambiguous("0*0")
    assert not is_one_unambiguous("0*0")
    assert is_one_unambiguous("(01)*")


# ---------------------------------------------------------------- parse errors
@pytest.mark.parametrize("r", ["2", "0|1", "(0", "0)", "*0", "a"])
def test_parse_errors(r):
    with pytest.raises(ValueError):
        parse(r)


# ------------------------------------------------- witness words really are ambiguous
def count_parses(node, w):
    """Number of parse trees of w (star iterations must be non-empty)."""
    @lru_cache(None)
    def go(n, i, j):
        k = n[0]
        if k == "eps":
            return 1 if i == j else 0
        if k == "sym":
            return 1 if j == i + 1 and w[i] == n[1] else 0
        if k == "cat":
            return sum(go(n[1], i, m) * go(n[2], m, j) for m in range(i, j + 1))
        if k == "star":
            if i == j:
                return 1
            return sum(go(n[1], i, m) * go(n, m, j) for m in range(i + 1, j + 1))
    return go(node, 0, len(w))


def brute_force_unambiguous(r, max_len=8):
    node = parse(r)
    for n in range(max_len + 1):
        for bits in itertools.product("01", repeat=n):
            if count_parses(node, "".join(bits)) > 1:
                return False
    return True


def random_regex(depth):
    if depth == 0 or random.random() < 0.3:
        return random.choice("01")
    t = random.random()
    if t < 0.4:
        return random_regex(depth - 1) + random_regex(depth - 1)
    if t < 0.8:
        return "(" + random_regex(depth - 1) + ")*"
    return "(" + random_regex(depth - 1) + random_regex(depth - 1) + ")"


def test_matches_brute_force_on_random_regexes():
    random.seed(0)
    checked = 0
    for _ in range(300):
        r = random_regex(3)
        if eps_ambiguous(parse(r)):
            continue  # the brute-force oracle skips empty iterations
        checked += 1
        assert is_unambiguous(r) == brute_force_unambiguous(r), r
    assert checked > 100


def test_witness_has_multiple_parses():
    for r in ["0*0*", "(00)*(000)*", "0*0*1"]:
        w = find_ambiguity(r)
        assert w is not None
        assert count_parses(parse(r), w) > 1, (r, w)
