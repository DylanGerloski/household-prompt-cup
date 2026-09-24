"""The household-command prompt cup, from a clean clone, in one command:

  pip install playwright && playwright install chromium      (once per machine)
  python cup.py                                              (all eleven prompts; about 11 minutes each)
  python cup.py --members plain-1 P10                        (a subset)

What it does, in order:
1. Makes sure site/needle.js, site/needle.wasm and site/needle3.cact are present and match the pinned sha256
   (Cactus-Compute/needle3 at revision 0f51a1ac, Apache 2.0, see NOTICE). A missing file is downloaded from that
   revision on huggingface.co, or copied from --weights DIR, and refused unless its sha256 matches.
2. Builds the leaderboard's recorded runs (site/replay_*.json, labels.json and the no-facts gate's home names) from
   the skeletons in data/ and the assist-mini dataset, fetched from allenporter/home-assistant-datasets at the
   leaderboard's pinned commit (or copied from --dataset DIR), and refuses unless every rebuilt file matches its pinned
   sha256 (dataset.py). The dataset carries no licence, so this repo holds none of its text.
3. For each prompt, opens site/replay.html in headless Chromium, served from 127.0.0.1, and runs needle in the page on
   every recorded command (196 per prompt): the same system text, tools and command text the leaderboard run gave it.
4. Scores each command the page answered with the leaderboard's own label for that answer (site/labels.json), and
   prints the table beside the leaderboard's own count, and how many of the 49 commands (each run four times)
   land differently from plain-1's leaderboard run. The table is written to RESULTS.md by this command, never typed.

Exit 0 only if every prompt's page count is within one command (4 tasks, one command's four repeats) of the
leaderboard's count and no request left 127.0.0.1 after the files were in place; exit 1 otherwise, with the table
written either way. One command is the page's own noise: its three runs of the unchanged prompt
land 12, 11 and 16, because the page and native needle break some near ties differently on different date lines and
tool orders. An answer no leaderboard run ever made has no label and is counted UNSCORED, so nobody reads the table
as call-exact.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys
import urllib.request

import dataset
from build_labels import case
from run_page import run
from score_reading import score

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")
REVISION = "0f51a1ac2917a03644c4cc7836f19476c6d177dd"
PINNED = {  # file in site/ -> (path in the needle3 repo, sha256)
    "needle.js": ("wasm/needle.js", "d00ec67ec7e03e4720dfc6c3dad95a0540afd00169a983ce3fabcd7aeaa0fa93"),
    "needle.wasm": ("wasm/needle.wasm", "77c6a38cacb8efbeebfd5202082ba9a0850a7c3066db40d4d0e80509cd137d9b"),
    "needle3.cact": ("needle3.cact", "c9d915eca282ed42d1a09b143b592adb4cc6744ffe2d294adf5cfc5548170c38"),
}
MEMBERS = ("plain-1", "plain-2", "plain-3", "P6", "P7", "P8", "P9", "P10", "P11", "P12", "P13")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ensure_files(weights=None):
    """Returns [(file, 'present'|'copied'|'downloaded')]. Raises SystemExit on a mismatch."""
    out = []
    for name, (repo_path, want) in PINNED.items():
        dest = os.path.join(SITE, name)
        how = "present"
        if not os.path.exists(dest):
            src = os.path.join(weights, name) if weights else None
            if src and os.path.exists(src):
                shutil.copyfile(src, dest + ".part")
                how = "copied"
            else:
                url = "https://huggingface.co/Cactus-Compute/needle3/resolve/%s/%s" % (REVISION, repo_path)
                print("downloading %s" % url, flush=True)
                urllib.request.urlretrieve(url, dest + ".part")
                how = "downloaded"
            got = sha256(dest + ".part")
            if got != want:
                os.remove(dest + ".part")
                raise SystemExit("REFUSED: %s has sha256 %s, pinned %s; nothing was run" % (name, got, want))
            os.replace(dest + ".part", dest)
        elif sha256(dest) != want:
            raise SystemExit("REFUSED: site/%s does not match its pinned sha256 %s; nothing was run" % (name, want))
        out.append((name, how))
    return out


def per_command(replay_path):
    """{command: runs landed of 4} from a replay file's leaderboard labels."""
    with open(replay_path, encoding="utf-8") as f:
        tasks = json.load(f)["tasks"]
    out = {}
    for t in tasks:
        c = case(t["task_id"])
        out[c] = out.get(c, 0) + (t["label"] == "Good")
    return out


def moved(base, good_ids):
    """'+up/-down': commands landing on more / fewer of their four runs than plain-1's leaderboard run."""
    got = dict.fromkeys(base, 0)
    for i in good_ids:
        got[case(i)] += 1
    return "+%d/-%d" % (sum(got[c] > base[c] for c in base), sum(got[c] < base[c] for c in base))


ONE_COMMAND = 4  # one command's four repeats: the page's own noise (plain-1/2/3 land 12, 11, 16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", nargs="*", default=list(MEMBERS))
    ap.add_argument("--weights", help="a directory holding needle.js, needle.wasm and needle3.cact to copy from")
    ap.add_argument("--dataset", help="a directory holding assist-mini's files, instead of fetching them")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds per prompt")
    ap.add_argument("--readings", default=os.path.join(HERE, "readings"))
    a = ap.parse_args()
    for name, how in ensure_files(a.weights):
        print("site/%s %s, sha256 %s" % (name, how, PINNED[name][1]), flush=True)
    print("site/ data files built from data/ and the dataset at %s: %d, each matching its pin"
          % (dataset.REV[:8], dataset.ensure(a.dataset, net=not a.dataset)), flush=True)
    base = per_command(os.path.join(SITE, "replay_plain-1.json"))
    os.makedirs(a.readings, exist_ok=True)
    rows, ok = [], True
    for m in a.members:
        print("running %s in headless Chromium ..." % m, flush=True)
        r = run("replay.html?member=%s" % m, a.timeout)
        with open(os.path.join(a.readings, "cup_%s.json" % m), "w", encoding="utf-8") as f:
            json.dump(r, f)
        res = r["result"] or {}
        if "page_error" in res:
            rows.append((m, "ERROR", "", "", "", "", "", len(r["off_machine"]), r["seconds"]))
            ok = False
            print("  %s: page error %s" % (m, res["page_error"]), flush=True)
            continue
        s = score(res)
        same = not s["differ"]  # an UNSEEN on a CI-Good task is in differ; any left over are CI-Bad
        diff = s["good"] - s["ci_good"]
        ok = ok and abs(diff) <= ONE_COMMAND and not r["off_machine"]
        rows.append((m, s["good"], s["ci_good"], "%+d" % diff, moved(base, s["good_ids"]), "yes" if same else "NO (%d)" % len(s["differ"]),
                     len(s["unseen"]), len(r["off_machine"]), r["seconds"]))
        print("  %s: page %d of %d, leaderboard %d" % (m, s["good"], s["n"], s["ci_good"]), flush=True)
    head = ("prompt", "page landed /196", "leaderboard landed /196", "page minus leaderboard",
            "commands moved vs plain-1, up/down of 49",
            "same commands as leaderboard", "unscored answers (no leaderboard label)",
            "requests off machine", "seconds")
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(str(x) for x in row) + " |" for row in rows]
    table = "\n".join(lines)
    print(table)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(os.path.join(HERE, "RESULTS.md"), "w", encoding="utf-8") as f:
        f.write("# Results\n\nWritten by `python cup.py` at %s, needle3 revision %s. Do not edit by hand.\n\n%s\n\n"
                "%s\n" % (stamp, REVISION[:8], table, "Every prompt run lands within one command (4) of its leaderboard count." if ok
                else "At least one prompt lands more than one command (4) from its leaderboard count, or a request left the machine."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
