"""Checks that stay after the build, so a later edit cannot quietly undo them. Exit 0 only if every one holds.

  python selftest.py

1. NO NETWORK FALL-THROUGH. With no dataset in vendor/ and no DIR given, dataset.fetch() refuses and never opens a
   URL. Only cup.py passes net=True (its declared fetch at the pinned commit); a bare scan, punch or fill must not
   download anything (a bare scan in a fresh clone once fetched 21 files by hand).
2. NO DATASET TEXT TRACKED. If vendor/assist-mini is present, `dataset.scan()` finds no dataset string of 8+
   characters in any tracked file. Without vendor/ this check says SKIPPED, never PASS.
"""
import os
import sys
import tempfile
import urllib.request

import dataset


def no_fall_through():
    opened = []
    real_open, real_vendor = urllib.request.urlopen, dataset.VENDOR
    urllib.request.urlopen = lambda *a, **k: opened.append(a) or (_ for _ in ()).throw(RuntimeError("network"))
    try:
        with tempfile.TemporaryDirectory() as d:
            dataset.VENDOR = os.path.join(d, "assist-mini")
            try:
                dataset.fetch()
                return False, "fetch() returned without the dataset and without net"
            except SystemExit as e:
                msg = str(e.code)
            except RuntimeError:
                return False, "fetch() tried to open a URL"
    finally:
        urllib.request.urlopen, dataset.VENDOR = real_open, real_vendor
    if opened:
        return False, "fetch() opened %d URL(s)" % len(opened)
    if not msg.startswith("REFUSED:"):
        return False, "fetch() exited without its refusal: %r" % msg
    return True, msg


def no_dataset_text():
    if not os.path.isdir(dataset.VENDOR):
        return None, "vendor/assist-mini absent; run `python cup.py` once, then this"
    hits = dataset.scan()
    return not hits, "%d hit(s)%s" % (len(hits), "".join("\n    %s: %r" % h for h in hits))


def main():
    bad = 0
    for name, check in (("no network fall-through", no_fall_through), ("no dataset text tracked", no_dataset_text)):
        ok, why = check()
        print("%s  %s: %s" % ({True: "PASS", False: "FAIL", None: "SKIPPED"}[ok], name, why))
        bad += ok is False
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
