"""AT-5's inputs: the home's names as prompt_carries_no_facts.py reads them, and the cases the page must rule on
exactly as that file rules.

The page does not keep its own list of names. This writes site/home_names.json from prompt_carries_no_facts.home_names()
(pairs, not an object, so a name that looks like an integer keeps its order), and site/nofacts_cases.json: Forge's
frozen prompts v1 and v2, the gate's own selftest texts, and for every name in the home a sentence carrying it as
written, in capitals, with underscores as spaces, and with a letter glued on either side (which must NOT hit),
plus Unicode and punctuation edges. Each case carries the Python file's own verdict: its sorted hit rows (kind, name,
fixtures, span) and its exit code and last printed line. nofacts_check.html runs the same cases through
site/nofacts.js and refuses on any difference.

  python build_nofacts.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.normpath(os.path.join(HERE, "..", "..", "hometiny-run"))
FORGE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "forge", "needle53"))
sys.path.insert(0, GATE)
import prompt_carries_no_facts as gate  # noqa: E402


def verdict(text, spec, dom):
    p = [{"id": "X", "text": text}]
    rows = gate.check(p, spec, dom)
    buf = io.StringIO()
    code = gate.report(p, rows, out=buf)
    return {"rows": sorted([list(r[1:]) for r in rows]), "exit": code,
            "last_line": buf.getvalue().rstrip("\n").split("\n")[-1]}


def cases(spec, dom):
    texts = []
    for f in ("prompts_v1.json", "prompts_v2.json"):
        with open(os.path.join(FORGE, f), encoding="utf-8") as h:
            texts += [("forge/%s/%s" % (f, p["id"]), p["text"]) for p in json.load(h)["prompts"]]
    # the gate's own selftest texts; the home's one vacuum is read from the home, not written here (AT-6b)
    vac = next(k for k in spec if k.startswith("vacuum."))
    vname = next(k for k in spec if k.replace(" ", "_").lower() == vac.split(".", 1)[1])
    for i, t in enumerate(("Turn on the %s now." % vname, "act in the living room",
                           "call %s" % vac, "turn off the light", "Make exactly one tool call.",
                           "be quick, it is five o'clock", "that is fantastic, go ahead",
                           "improve the lighting situation", "go downstairs", "the Living Room light")):
        texts.append(("selftest/%d" % i, t))
    for i, n in enumerate(list(spec) + list(dom)):
        for j, t in enumerate(("please use %s now." % n, "%s!" % n.upper(), "(%s)" % n.replace("_", " "),
                               "x%s" % n, "%sx" % n, "a.%s b" % n, "%s_z" % n, "é%s" % n, "%sé" % n)):
            texts.append(("name/%d/%d" % (i, j), t))
    texts += [("edge/%d" % i, t) for i, t in enumerate((
        "", "İstanbul light", "😀 light 😀 Living Room " + "y" * 40, "LIGHT\nlock\tfan", "light.", ".light",
        "light-fan", "the living_room and the living room"))]
    return [{"id": cid, "text": t, **verdict(t, spec, dom)} for cid, t in texts]


def main():
    spec, dom = gate.home_names()
    with open(os.path.join(HERE, "site", "home_names.json"), "w", encoding="utf-8") as h:
        json.dump({"specific": list(spec.items()), "domain": list(dom.items()),
                   "fixtures": len(gate.fixture_files())}, h)
    cs = cases(spec, dom)
    with open(os.path.join(HERE, "site", "nofacts_cases.json"), "w", encoding="utf-8") as h:
        json.dump(cs, h)
    by = {}
    for c in cs:
        by[c["exit"]] = by.get(c["exit"], 0) + 1
    print("home: %d specific, %d domain, %d fixtures; %d cases, exits %s -> site/home_names.json, "
          "site/nofacts_cases.json" % (len(spec), len(dom), len(gate.fixture_files()), len(cs), dict(sorted(by.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
