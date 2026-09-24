"""The same replay as site/replay.html, through the Python cactus-needle wrapper on this box (c59/.venv, 3.0.4;
CI ran 3.0.1). Used only to triangulate a page/record gap: if Python reproduces the record where the page does
not, the page is wrong; if neither does, the rebuilt input is. Telemetry is off (NEEDLE_TELEMETRY=0), as CI's CI=1
had it.
  ../../c59/.venv/Scripts/python py_replay.py --member plain-1 [--limit N]
"""
import argparse
import json
import os
import sys
import time

os.environ["NEEDLE_TELEMETRY"] = "0"
import needle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def canon(v):
    return json.dumps(v, sort_keys=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--member", required=True)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    with open(os.path.join(HERE, "site", "replay_%s.json" % a.member), encoding="utf-8") as f:
        doc = json.load(f)
    tasks, match, t0 = [], 0, time.time()
    for t in doc["tasks"][:a.limit]:
        err, reply = None, None
        try:
            reply = needle.Needle(tools=doc["toolsets"][t["toolset"]], system=t["system"] or None).complete(t["text"])
        except Exception as e:  # noqa: BLE001  -- CI's agent turned any exception into a failed turn too
            err = str(e)
        calls = [{"name": c["name"], "arguments": c.get("arguments") or {}}
                 for c in (reply or {}).get("function_calls") or []] if reply and reply.get("type") == "call" else []
        ok = err is None and canon(calls) == canon(t["recorded_calls"])
        match += ok
        tasks.append({"task_id": t["task_id"], "calls": calls, "error": err, "matches_recorded": ok})
    out = os.path.join(HERE, "readings", "py_replay_%s.json" % a.member)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"member": a.member, "n": len(tasks), "match_recorded": match, "tasks": tasks}, f)
    print("%s: python needle %s matches the record on %d of %d in %.0fs -> %s" % (
        a.member, needle.__dict__.get("__version__", "?"), match, len(tasks), time.time() - t0, out))


if __name__ == "__main__":
    sys.exit(main())
