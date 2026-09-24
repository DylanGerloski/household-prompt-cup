"""Fetch needle's wasm build for c53 stage 1 (AT-1), pinned, once, logged.

The folder listing was read through webread at 2026-09-24T08:3xZ: Cactus-Compute/needle3 wasm/ holds needle.h,
needle.js, needle.wasm; the newest commit touching it is 0f51a1ac... ("Replace binaries from production build").
The fetch is c59_ready.fetch_pinned (Hearth #17279 item 2: once, no retry, every outcome logged to
territories/smith/c59/fetch_log.jsonl). Files land in ./vendor/<revision>/wasm/, and sha256 is printed from disk.

  python territories/smith/builds/c53-browser-cup/fetch_wasm.py
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "probe-kit"))
import c59_ready as c  # noqa: E402

REPO = "Cactus-Compute/needle3"
REVISION = "0f51a1ac2917a03644c4cc7836f19476c6d177dd"
FILES = ("wasm/needle.js", "wasm/needle.wasm", "wasm/needle.h", "LICENSE", "README.md")


def pins():
    return [{"repo_type": "model", "repo_id": REPO, "revision": REVISION, "filename": f} for f in FILES]


def main():
    root = os.path.join(HERE, "vendor", "hf")
    try:
        recs = c.fetch_pinned(pins(), root=root)
    except c.FetchStopped as e:
        print("STOPPED: %s" % e)
        return 3
    for r in recs:
        print("%s %s %s bytes sha256 %s" % (r["outcome"], r["filename"], r["bytes"], r["sha256"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
