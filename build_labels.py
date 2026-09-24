"""The page's scorer table: for every (task, calls) pair any of the eleven c53 members made in CI, the label CI's own
eval gave it (the leaderboard's expected-states check against the synthetic home, reset per task).

WHY A LOOKUP AND NOT A SIMULATOR: the label is what HA's intent matching plus the fixture home did with a call. A
re-implementation of that in the page would be a second scorer to validate; the lookup IS the first scorer's own
output. It is keyed on the task with its repeat suffix dropped (the -0..-3 repeats are the same case in the same
freshly loaded home), so a call any member made on any repeat carries its label. The build REFUSES if one key ever
got two labels -- that is the validation against all eleven members' (call, label) pairs. A page call no member made
is not guessed: the page counts it UNSEEN and prints it, and a count with an UNSEEN in it is not a parity claim.
ONE RULE BEYOND THE LOOKUP: every task carries expect_changes, and a turn whose calls are all GetLiveContext (or none)
changes nothing, so it is Bad without a lookup. The build refuses unless every such key in CI's records is Bad.

  .venv/Scripts/python build_labels.py      (after build_replay.py for each member)
Writes site/labels.json: {"<case>\t<canonical calls>": "Good"|"Bad"|...}.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def case(task_id):
    return re.sub(r"-\d+$", "", task_id)


def canon(calls):
    return json.dumps([{"name": c["name"], "arguments": c.get("arguments") or {}} for c in calls], sort_keys=True)


READ_ONLY = "homeassistant__GetLiveContext"


def read_only(calls):
    return all(c["name"] == READ_ONLY for c in calls)


def main():
    table, where, conflicts, members = {}, {}, [], []
    for f in sorted(glob.glob(os.path.join(HERE, "site", "replay_*.json"))):
        with open(f, encoding="utf-8") as h:
            doc = json.load(h)
        members.append(doc["member"])
        for t in doc["tasks"]:
            if t["label"] is None:
                continue
            if not t["expect_changes"]:
                conflicts.append(("no expect_changes", doc["member"], t["task_id"], "", ""))
            if read_only(t["recorded_calls"]) and t["label"] != "Bad":
                conflicts.append(("read-only call labelled %s" % t["label"], doc["member"], t["task_id"], "", ""))
            k = case(t["task_id"]) + "\t" + canon(t["recorded_calls"])
            if k in table and table[k] != t["label"]:
                conflicts.append((k, table[k], where[k], t["label"], "%s/%s" % (doc["member"], t["task_id"])))
            table.setdefault(k, t["label"])
            where.setdefault(k, "%s/%s" % (doc["member"], t["task_id"]))
    for c in conflicts[:20]:
        print("CONFLICT", c)
    if conflicts:
        print("REFUSED: %d conflicts (two labels on a key, or the read-only rule broken); not a scorer" % len(conflicts))
        return 2
    with open(os.path.join(HERE, "site", "labels.json"), "w", encoding="utf-8") as h:
        json.dump(table, h, sort_keys=True)
    ro = sum(1 for k in table if read_only(json.loads(k.split("	")[1])))
    print("%d members (%s): %d distinct (case, calls) keys, %d Good, %d read-only all Bad, 0 conflicts -> "
          "site/labels.json" % (len(members), ", ".join(members), len(table),
                                sum(1 for v in table.values() if v == "Good"), ro))
    return 0


if __name__ == "__main__":
    sys.exit(main())
