"""Diff a fresh RESULTS.md against the one committed at HEAD, leaving out only what changes on every run.

  python results_diff.py [FILE]    # FILE defaults to RESULTS.md; exit 0 only on a diff of zero lines

The stamp line ("Written by `python cup.py` at ...") and the last column (seconds) are dropped from both sides,
because they are the wall clock, not the result; every other byte is compared.
"""
import difflib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def steady(text):
    out = []
    for line in text.splitlines():
        if line.startswith("Written by `python cup.py` at "):
            continue
        if line.startswith("|"):
            line = "|".join(line.rstrip().rstrip("|").split("|")[:-1]) + "|"
        out.append(line)
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "RESULTS.md")
    head = subprocess.run(["git", "show", "HEAD:RESULTS.md"], cwd=HERE, capture_output=True, check=True).stdout
    with open(path, "rb") as f:
        new = f.read()
    d = list(difflib.unified_diff(steady(head.decode("utf-8")), steady(new.decode("utf-8")),
                                  "HEAD:RESULTS.md", path, lineterm=""))
    print("\n".join(d))
    print("%d differing line(s), stamp line and seconds column left out" % sum(
        1 for x in d if x[:1] in "+-" and x[:3] not in ("+++", "---")))
    return 1 if d else 0


if __name__ == "__main__":
    sys.exit(main())
