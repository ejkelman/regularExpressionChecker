# regex-ambiguity

Decides whether a regular expression over {0, 1} (using only `0`, `1`, `*`, `(`, `)`) is unambiguous.

    python regex_ambiguity.py "0*0*"    # False (ambiguous word: '0')
    python regex_ambiguity.py "(01)*"   # True

Run tests:

    pip install pytest
    pytest
