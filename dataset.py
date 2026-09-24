"""The assist-mini dataset, fetched and never committed (spec AT-6b).

allenporter/home-assistant-datasets carries no licence, so this repo holds no file taken from it. The page's data
files (site/replay_*.json, labels.json, home_names.json, nofacts_cases.json) are committed as SKELETONS under data/:
the same bytes with every string that appears in the dataset cut out and replaced by a numbered hole. `fill` puts
the strings back from the dataset itself, fetched at the leaderboard's pinned commit, and the result must match the
sha256 pinned in data/pins.json byte for byte, or nothing is written.

The string table is every scalar value in the 21 files below, as each line reads with its whitespace collapsed (so a
raw file and a whitespace-flattened copy of it give the same table), plus the folder names, each in the forms the eval
harness writes it: as-is, lower case, slugged (task ids, entity ids) and JSON-escaped. Strings shorter than four
characters and all-digit strings stay in place; they are states and numbers, not the dataset's writing.

  python dataset.py punch      # maintainer: site/ -> data/*.skel + data/pins.json (needs the dataset in vendor/)
  python dataset.py fill       # anyone: data/*.skel + vendor/assist-mini -> site/, checked against the pins
  python dataset.py scan       # exit 1 if any tracked file carries a dataset string of 8+ characters
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REV = "45e9ac2e998f3308007322aada2eae92afd198c2"  # hometiny-run/ci_run.sh LEADERBOARD_SHA, the runs' own pin
BASE = "https://raw.githubusercontent.com/allenporter/home-assistant-datasets/%s/" % REV
FILES = ["datasets/assist-mini/" + f for f in (
    "dataset_card.yaml",
    "dom1-pl-lights/_fixtures.yaml", "dom1-pl-lights/lights.yaml",
    "dom1-pl-todo/_fixtures.yaml", "dom1-pl-todo/todo.yaml",
    "home1-us-cover-garage/_fixtures.yaml", "home1-us-cover-garage/cover-garage.yaml",
    "home1-us-lock/_fixtures.yaml", "home1-us-lock/smart-lock.yaml",
    "home1-us-vacuum/_fixtures.yaml", "home1-us-vacuum/vacuum.yaml",
    "home2-ru-valve/_fixtures.yaml", "home2-ru-valve/water-valve.yaml",
    "home5-cn-fan/_fixtures.yaml", "home5-cn-fan/fan.yaml",
    "home5-cn-light/_fixtures.yaml", "home5-cn-light/light.yaml",
    "home7-dk-cover-curtain/_fixtures.yaml", "home7-dk-cover-curtain/cover-curtain.yaml",
    "home7-dk-media-player/_fixtures.yaml", "home7-dk-media-player/media-player.yaml")]
VENDOR = os.path.join(HERE, "vendor", "assist-mini")
DATA = os.path.join(HERE, "data")
PINS = os.path.join(DATA, "pins.json")
BUILT = ["site/home_names.json", "site/labels.json", "site/nofacts_cases.json"] + [
    "site/replay_%s.json" % m for m in ["plain-1", "plain-2", "plain-3"] + ["P%d" % i for i in range(6, 14)]]
HOLE = "⟦%d⟧"  # a hole reads as a bracketed number; no dataset string holds these brackets
HOLE_RE = re.compile("⟦(\\d+)⟧")


def fetch(src=None, net=False):
    """{path: text} for the 21 files: from vendor/ if present, else from src DIR, else downloaded at REV, and only
    when net is True. Only cup.py passes net (its declared fetch, like needle's); scan, punch and a bare fill never
    touch the network, so a maintainer's check cannot become an unlogged read."""
    out = {}
    for f in FILES:
        dst = os.path.join(VENDOR, f.split("assist-mini/")[1])
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if src:
                with open(os.path.join(src, f.split("assist-mini/")[1]), "rb") as h:
                    body = h.read()
            elif not net:
                sys.exit("REFUSED: %s is not in vendor/ and no DIR was given; `python cup.py` fetches it, or pass "
                         "the dataset's directory" % f)
            else:
                with urllib.request.urlopen(BASE + f, timeout=60) as r:
                    body = r.read()
            with open(dst, "wb") as h:
                h.write(body)
        with open(dst, encoding="utf-8") as h:
            out[f] = h.read()
    return out


def values(text):
    """Every scalar value in one YAML file, read line by line with whitespace collapsed."""
    for line in text.splitlines():
        s = " ".join(line.split())
        while s.startswith("- "):
            s = s[2:]
        if s in ("", "---", "-") or s.endswith(":") and " " not in s:
            continue
        m = re.match(r"^[\w.\-]+: (.*)$", s)
        v = m.group(1) if m else s
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        yield v


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def table(texts):
    """The ordered string table: longest first, so a longer string is cut before any string inside it."""
    base = set()
    for f, t in texts.items():
        base.update(values(t))
        base.add(f.split("/")[2])
    forms = set()
    for v in base:
        for x in (v, v.lower(), slug(v), v.replace("-", "_")):
            for y in (x, json.dumps(x)[1:-1]):
                if len(y) >= 4 and not y.isdigit():
                    forms.add(y)
    return sorted(forms, key=lambda s: (-len(s), s))


def punch(text, tab):
    for i, s in enumerate(tab):
        if s in text:
            text = text.replace(s, HOLE % i)
    return text


def fill(text, tab):
    return HOLE_RE.sub(lambda m: tab[int(m.group(1))], text)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def cmd_punch():
    tab = table(fetch())
    os.makedirs(DATA, exist_ok=True)
    pins = {}
    for p in BUILT:
        with open(os.path.join(HERE, p), encoding="utf-8", newline="") as h:
            text = h.read()
        sk = punch(text, tab)
        if fill(sk, tab) != text:
            sys.exit("REFUSED: %s does not round-trip; nothing written" % p)
        pins[p] = sha(text.encode("utf-8"))
        with open(os.path.join(DATA, os.path.basename(p) + ".skel"), "w", encoding="utf-8", newline="") as h:
            h.write(sk)
    pins["_table"] = sha(json.dumps(tab).encode("utf-8"))
    with open(PINS, "w", encoding="utf-8") as h:
        json.dump({"rev": REV, "sha256": pins}, h, indent=1, sort_keys=True)
    print("punched %d files, table of %d strings, pins in data/pins.json" % (len(BUILT), len(tab)))


def ensure(src=None, net=False):
    """Build every site/ data file from its skeleton; refuse, writing nothing, on any pin mismatch."""
    with open(PINS, encoding="utf-8") as h:
        pins = json.load(h)["sha256"]
    tab = table(fetch(src, net))
    if sha(json.dumps(tab).encode("utf-8")) != pins["_table"]:
        sys.exit("REFUSED: the fetched dataset gives a different string table than the pinned one; nothing written")
    out = {}
    for p in BUILT:
        with open(os.path.join(DATA, os.path.basename(p) + ".skel"), encoding="utf-8", newline="") as h:
            text = fill(h.read(), tab)
        if sha(text.encode("utf-8")) != pins[p]:
            sys.exit("REFUSED: %s rebuilt with sha256 %s, pinned %s; nothing written" % (p, sha(text.encode("utf-8")), pins[p]))
        out[p] = text
    for p, text in out.items():
        with open(os.path.join(HERE, p), "w", encoding="utf-8", newline="") as h:
            h.write(text)
    return len(out)


# Strings the dataset shares with something this repo cites or wrote on its own, each with where it comes from. A
# new entry here is a claim a reviewer can check; nothing else is let through.
NOT_TAKEN = {
    "assist-mini": "the dataset's name, cited as the source (nofacts.js, README)",
    "volume_level": "Home Assistant's own HassSetVolume slot name (build_replay.py's tool schema)",
    "brightness": "Home Assistant's own HassLightSet slot name (build_replay.py's tool schema)",
    "kitchen light": "AT-1's smoke-test command, written for at1.html with a one-tool toolset of its own",
    "Living Room": "a plain room name, in the no-facts gate's own selftest texts (build_nofacts.py)",
    "living room": "the same, lower case",
    "living_room": "the same, as an id",
}


def scan(tab=None, min_len=8):
    """[(tracked file, dataset string)] for every tracked file holding a dataset string of min_len+ characters."""
    tab = tab or table(fetch())
    # the folder and file names in FILES are the addresses this repo fetches from, a citation and not content
    where = {x for f in FILES for part in f.split("/") for x in (part, os.path.splitext(part)[0])}
    long_ = [s for s in tab if len(s) >= min_len and s not in NOT_TAKEN and s not in where]
    files = subprocess.run(["git", "ls-files"], cwd=HERE, capture_output=True, text=True, check=True).stdout.split("\n")
    hits = []
    for f in filter(None, files):
        try:
            with open(os.path.join(HERE, f), encoding="utf-8") as h:
                t = h.read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        hits += [(f, s) for s in long_ if s in t]
    return hits


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "punch":
        cmd_punch()
    elif what == "fill":
        print("filled %d files, every one matching its pin" % ensure(sys.argv[2] if len(sys.argv) > 2 else None))
    elif what == "scan":
        h = scan()
        for f, s in h:
            print("DATASET TEXT %s: %r" % (f, s))
        print("%d tracked file(s) carry dataset text" % len({f for f, _ in h}))
        sys.exit(1 if h else 0)
    else:
        sys.exit(__doc__)
