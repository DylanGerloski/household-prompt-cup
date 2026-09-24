"""Serve site/ on 127.0.0.1 and open one page in headless Chromium (Playwright's own build on this box).

Every request the page makes is logged with its URL; any request whose host is not 127.0.0.1 is counted as OFF-MACHINE
(AT-2's reading). Prints window.RESULT as JSON once the page sets it.

  python run_page.py at1.html [--timeout 300]
  python run_page.py "replay.html?member=plain-1" --timeout 3600 --out readings/replay_plain-1.json
"""
import argparse
import functools
import http.server
import json
import os
import sys
import threading
import time
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site")


class Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".wasm": "application/wasm",
                      ".js": "text/javascript"}

    served = []  # every path the local server answered; needle.wasm in here is the cold first download (AT-2)

    def log_message(self, *a):
        pass

    def do_GET(self):
        Quiet.served.append(self.path)
        return super().do_GET()


def serve():
    h = functools.partial(Quiet, directory=SITE)
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def run(page, timeout_s=300, context=None):
    from playwright.sync_api import sync_playwright
    s = serve()
    base = "http://127.0.0.1:%d/" % s.server_address[1]
    reqs = []
    t0 = time.time()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context()  # a fresh in-memory profile: empty HTTP cache, so every run starts cold
        blocked, sockets = [], []
        # Every request the context makes, workers included, passes this route. Off-machine ones are recorded and
        # aborted, so a hidden call cannot succeed, and it cannot pass uncounted either.
        ctx.route("**/*", lambda rt: (blocked.append(rt.request.url), rt.abort())
                  if urlparse(rt.request.url).hostname != "127.0.0.1" else rt.continue_())
        ctx.on("request", lambda r: reqs.append(r.url))
        # A WebSocket never passes ctx.route and can fail before the page's "websocket" event fires (the at2_control
        # page proved both); route_web_socket sees every one. An off-machine socket is recorded and left unconnected:
        # a routed socket that is never connected to its server reaches no server (calling ws.close() here hung).
        ctx.route_web_socket("**/*", lambda ws: sockets.append(ws.url)
                             if urlparse(ws.url).hostname != "127.0.0.1" else ws.connect_to_server())
        pg = ctx.new_page()
        pg.on("websocket", lambda w: sockets.append(w.url))
        Quiet.served.clear()
        msgs = []
        pg.on("console", lambda m: msgs.append(m.text))
        errs = []  # a module that fails to parse never reaches its own catch; only this sees it
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + page)
        deadline = time.time() + timeout_s
        while not errs and not pg.evaluate("window.RESULT !== undefined"):
            if time.time() > deadline:
                errs.append("TIMEOUT after %ss with no window.RESULT" % timeout_s)
            pg.wait_for_timeout(500)
        result = pg.evaluate("window.RESULT") if not errs else {"page_error": errs[:5]}
        b.close()
    s.shutdown()
    off = sorted(set([u for u in reqs if urlparse(u).hostname not in ("127.0.0.1",)] + blocked + sockets))
    return {"result": result, "requests": len(reqs), "off_machine": off, "seconds": round(time.time() - t0, 1),
            "cold": {"served": sorted(set(Quiet.served)), "websockets": sockets, "blocked": blocked},
            "console_tail": msgs[-5:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out", help="write the whole reading here as JSON; stdout then carries all but result.tasks")
    a = ap.parse_args()
    r = run(a.page, a.timeout)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f)
        r = {**r, "result": {k: v for k, v in (r["result"] or {}).items() if k != "tasks"}}
    print(json.dumps(r, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
