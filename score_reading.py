"""Score a page reading (run_page.py --out) with site/labels.json, CI's own labels (build_labels.py).

Prints Good / Bad / UNSEEN and CI's recorded Good count for the member. A call no member made in CI is UNSEEN, listed
by text (a read-only turn is Bad by build_labels' checked rule, not UNSEEN), and the score is then printed as a
range, never as a parity claim.
  .venv/Scripts/python score_reading.py readings/replay_plain-1.json
"""
import json
import os
import sys

from build_labels import canon, case, read_only

HERE = os.path.dirname(os.path.abspath(__file__))


def score(r):
    """{member, good, bad, unseen:[(task, text, calls)], ci_good, differ:[(task, ci, page)], n} for one page result."""
    with open(os.path.join(HERE, "site", "labels.json"), encoding="utf-8") as h:
        lab = json.load(h)
    with open(os.path.join(HERE, "site", "replay_%s.json" % r["member"]), encoding="utf-8") as h:
        rec = {t["task_id"]: t for t in json.load(h)["tasks"]}
    good = bad = 0
    unseen, differ, good_ids = [], [], []
    for t in r["tasks"]:
        k = case(t["task_id"]) + "\t" + canon(t["calls"] or [])
        v = lab.get(k) or ("Bad" if read_only(t["calls"] or []) else None)
        if v is None:
            unseen.append((t["task_id"], rec[t["task_id"]]["text"], canon(t["calls"] or [])))
        elif v == "Good":
            good += 1
            good_ids.append(t["task_id"])
        else:
            bad += 1
        if (v == "Good") != (rec[t["task_id"]]["label"] == "Good"):
            differ.append((t["task_id"], rec[t["task_id"]]["label"], v or "UNSEEN"))
    return {"member": r["member"], "n": len(r["tasks"]), "good": good, "bad": bad, "unseen": unseen,
            "ci_good": sum(1 for t in rec.values() if t["label"] == "Good"), "differ": differ, "good_ids": good_ids}


def main(path):
    with open(path, encoding="utf-8") as h:
        r = json.load(h)
    s = score(r.get("result", r))
    print("%s: page Good %d, Bad %d, UNSEEN %d of %d; CI recorded Good %d; tasks whose Good-ness differs from CI: %d"
          % (s["member"], s["good"], s["bad"], len(s["unseen"]), s["n"], s["ci_good"], len(s["differ"])))
    for u in s["unseen"]:
        print("  UNSEEN %s | %s | %s" % u)
    for d in s["differ"]:
        print("  DIFFERS %s CI %s page %s" % d)
    if s["unseen"]:
        print("  score range %d..%d; %s" % (s["good"], s["good"] + len(s["unseen"]), "every UNSEEN is a task CI scored "
              "Bad, so the Good ids still match CI (Architect #19957 item 1)" if not s["differ"] else "not a parity claim"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
