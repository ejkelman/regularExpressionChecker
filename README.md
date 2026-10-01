This project was inspired by the course material of MATH 249 - Introduction to Combinatorics (Advanced Level), taken at University of Waterloo and taught by Professor Stephen Melczer. See more of the course material at enumeration.ca

# regex-ambiguity

A Python tool that determines whether a regular expression of the alphabet {0, 1} is unambiguous.

## Allowed syntax

Only these characters are accepted:

| `0`, `1` | 
| `*` | 
| `(` `)` | 



## Quick start

```
python3 regex_ambiguity.py "0*0*"    # False  (ambiguous word: '0')
python3 regex_ambiguity.py "(01)*"   # True
```

Or from Python:

```python
from regex_ambiguity import is_unambiguous, find_ambiguity

is_unambiguous("(01)*")      # True
is_unambiguous("0*0*")       # False
find_ambiguity("0*0*")       # '0'   (a word that can be matched in 2+ ways)
find_ambiguity("(01)*")      # None  (unambiguous)
```

## What on earth are you talking about?

A **regular expression** is an expression of characters (in this case '0' and '1') and rules to combine them. It specifies a set of strings that can be constructed using that expression (which we call a **regular language**) . An expression is called **unambiguous** if there is only one way to get from the expression to each word in the language, and **ambiguous** if there exists a word that you can get to from the expression in more than one way. 

### Examples

**`0*0*` is ambiguous.** The word `0` matches two ways: the first `0*` takes the `0` and the second takes nothing, or the first takes nothing and the second takes the `0`. Both give the same word, but they are different matches.

**`(01)*` is unambiguous.** Any word it accepts (`ε`, `01`, `0101`, ...) can only be split into `01` blocks one way.

**`0*1*` is unambiguous.** In any word like `0011`, the boundary between the 0s and the 1s is forced.

**`0*0` is unambiguous**, even though it looks similar to `0*0*`. The final `0` is mandatory, so the split of `000` is always "`00` from the star, then `0`".

**`(0*)*` is ambiguous.** The inner `0*` can match the empty word, so the outer star can repeat "nothing" any number of times. The empty word therefore has infinitely many matches. This tool treats any star over something that can match the empty word as ambiguous.

Ambiguity is a property of the *expression*, not of the language it describes. `0*0*` and `0*` lead to exactly the same words, but `0*` is unambiguous and `0*0*` is not.


## How the algorithm works

The check runs in four steps.

### 1. Parse

The input string is parsed by a small recursive-descent parser into a tree with four node types:

- `eps` (empty word)
- `sym` (a `0` or `1`)
- `cat` (concatenation of two parts)
- `star` (repetition)

Illegal characters, unbalanced parentheses, and a `*` with nothing to repeat raise a `ValueError`.

### 2. Check for empty-word ambiguity

For every subexpression, the code counts how many ways it can match the empty word (capped at 2). A star over anything that can match the empty word counts as 2, so such expressions are immediately reported ambiguous with the empty word as the witness. Doing this first also avoids loops of empty matches in the next step.

### 3. Build the Glushkov (position) automaton

Each symbol occurrence in the regex is numbered. For `0*0*`, that's `0₁* 0₂*`. The automaton has one state per position plus a start state. It is built by computing, bottom-up over the tree:

- **nullable**: can this part match the empty word?
- **first**: which positions can start a match?
- **last**: which positions can end a match?
- **follow**: which positions can come immediately after a given position?

From these, the transitions are:
- start → each position in `first`, labeled by that position's symbol
- position `p` → each position in `follow(p)`, labeled by that position's symbol

The accepting states are the positions in `last` (plus the start state if the regex is nullable).

This automaton has no empty transitions, and each distinct way of matching a word corresponds to exactly one path through it. So the regex is ambiguous exactly when some word has two different accepting paths.

### 4. Search the product automaton

To find two different paths on the same word, the code builds the **product** of the automaton with itself. A product state is a pair `(p, q)`, and it moves on a symbol only if both components can move on it. Walking in the product means "two runs reading the same word in lockstep".

The regex is **ambiguous if and only if** there is a pair `(p, q)` with `p ≠ q` that is:

- **reachable** from `(start, start)`, meaning two runs can read the same prefix and end up in different states, and
- **co-reachable**, meaning from there both runs can continue on a common suffix and both end in accepting states.

Reachability and co-reachability are both found with a breadth-first search. The search also records how it got there, so the tool can return an actual ambiguous word (the prefix that reaches the pair plus the suffix that finishes it).

### Complexity

With `n` symbol occurrences in the regex, the product has up to `n²` states, so the whole check runs in polynomial time (roughly `O(n⁴)` in the worst case with this simple implementation), which is instant for any regex a person would write.

## Extra: one-unambiguity

`is_one_unambiguous(regex)` checks a stricter property used by deterministic matchers (and XML schema languages): after reading each symbol, the next position is determined by one character of lookahead. Every one-unambiguous regex is unambiguous, but not the reverse. For example, `0*0` is unambiguous but not one-unambiguous, because on reading a `0` you can't yet tell whether it is the last one.


## Running the tests

Install pytest (once), then run it from the repo folder:

```
pip install pytest
pytest
```

The tests cover:

1. **Known cases**: lists of regexes that must come out ambiguous or unambiguous.
2. **Error handling**: bad input must raise `ValueError`.
3. **Brute-force comparison**: for 300 random regexes, the algorithm's answer is compared against a slow but obviously correct method that counts the matches of every binary word up to length 8.
4. **Witness check**: the ambiguous word the tool returns must really have more than one match.
