"""Rebuild, per recorded task, the exact (system, tools_json, text) the CI agent handed Needle, and write it
beside the recorded call and label so the page can replay it.

WHY A REBUILD: the run reports keep each tool's parameters only as a Python repr, which loses Required/Optional
and slot descriptions. The CI agent (hometiny-run conversation.py) rendered them with
probatio.to_openapi(tool.parameters, custom_serializer=selector_serializer) under Home Assistant 2026.9.2, which
installs probatio AS voluptuous. So this file does the same: the repr is evaluated back into probatio schemas,
each key gets the marker and description HA 2026.9.2's own source gives it (MARKS, read from the wheel in
vendor/ha), and probatio 0.11.4 renders it. Needle then received json.dumps(tools) -- Python's separators -- and
a system text prefixed by needle._with_date_fact from the runner clock; both are reproduced here, the date from
the task's own async_process stamp (UTC runner), and a task whose turn straddles a minute is marked.

  .venv/Scripts/python build_replay.py --member plain-1
Writes site/replay_<member>.json. Reads the kiln tree's variance_runs; writes nothing there.
"""
import argparse
import csv
import datetime
import glob
import json
import os
import re
import sys
from typing import Any

from probatio.compat import install_as_voluptuous

install_as_voluptuous()
import voluptuous as vol  # noqa: E402  (probatio, as HA 2026.9.2 imports it)
from probatio import UNSUPPORTED, to_openapi  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.normpath(os.path.join(HERE, "..", "..", "hometiny-run", "variance_runs", "c53-needle3-prompt-v2"))


# Stand-ins with HA 2026.9.2's own signatures (probatio renders an unhandled callable by its first parameter's hint).
def string(value: Any) -> str:  # cv.string, config_validation.py:697
    return str(value)


def non_empty_string(value: Any) -> str:  # intent.non_empty_string, intent.py:867
    return str(value)


def ensure_list[_T](value: _T | None) -> list[_T] | list[Any]:  # cv.ensure_list, config_validation.py:353
    return value if isinstance(value, list) else [value]


def color_name_to_rgb(color_name: str):  # util/color.py:198
    return color_name


def selector_serializer(schema: Any) -> Any:  # helpers/llm.py:411, the branches these tools reach
    if schema is string or schema is non_empty_string:
        return {"type": "string"}
    return UNSUPPORTED


BRIGHT = "The brightness percentage of the light between 0 and 100, where 0 is off and 100 is fully lit"
MARKS = {  # (intent or tool, key) -> (Required?, description, default); from the HA 2026.9.2 sources named
    ("GetLiveContext", "name"): (False, "Filter entities by name or alias (case-insensitive).", None),
    ("GetLiveContext", "domain"): (False, "Filter entities by domain (e.g. 'light', 'sensor'). Accepts a single "
                                          "domain or a list.", None),
    ("GetLiveContext", "area"): (False, "Filter entities by area name or alias (case-insensitive).", None),
    ("*", "domain"): (False, None, None),  # intent.py:954
    ("*", "device_class"): (False, None, None),  # intent.py:968
    ("HassLightSet", "color"): (False, None, None),
    ("HassLightSet", "temperature"): (False, None, None),
    ("HassLightSet", "brightness"): (False, BRIGHT, None),
    ("HassFanSetSpeed", "percentage"): (True, "The speed percentage of the fan", None),
    ("HassSetPosition", "position"): (True, None, None),
    ("HassSetVolume", "volume_level"): (True, "The volume percentage of the media player", None),
    ("HassMediaPlayerMute", "is_volume_muted"): (False, "Whether the media player should be muted or unmuted", None),
    ("HassMediaPlayerUnmute", "is_volume_muted"): (False, "Whether the media player should be muted or unmuted",
                                                   None),
    ("HassCancelAllTimers", "area"): (False, None, None),
    ("get_items", "todo_list"): (True, None, None),
    ("get_items", "status"): (False, "Filter returned items by status, by default returns incomplete items",
                              "needs_action"),
    ("HassListAddItem", "item"): (True, None, None), ("HassListAddItem", "name"): (True, None, None),
    ("HassListCompleteItem", "item"): (True, None, None), ("HassListCompleteItem", "name"): (True, None, None),
    ("HassListRemoveItem", "item"): (True, None, None), ("HassListRemoveItem", "name"): (True, None, None),
    ("HassVacuumCleanArea", "area"): (True, None, None), ("HassVacuumCleanArea", "name"): (False, None, None),
    ("HassSetVolumeRelative", "volume_step"): (True, None, None),
    ("HassMediaSearchAndPlay", "search_query"): (True, None, None),
    ("HassMediaSearchAndPlay", "media_class"): (False, None, None),
}
for _i in ("HassSetVolumeRelative", "HassMediaSearchAndPlay"):
    for _k in ("name", "area", "floor"):
        MARKS[(_i, _k)] = (False, None, None)


class Unmapped(Exception):
    pass


def _eval_repr(text):
    t = re.sub(r" at 0x[0-9a-f]+", "", text)
    t = re.sub(r"<function [\w.<>]*<lambda>>", "_LAMBDA", t)
    t = t.replace("<function Boolean>", "vol.Boolean()")
    t = re.sub(r"<function (string|non_empty_string|ensure_list|color_name_to_rgb)>", r"\1", t)
    if "<" in t:
        raise Unmapped("unmapped token in repr: %s" % t[:200])
    ns = {"vol": vol, "Any": vol.Any, "All": vol.All, "In": vol.In, "Coerce": vol.Coerce, "Range": vol.Range,
          "string": string, "non_empty_string": non_empty_string, "ensure_list": ensure_list,
          "color_name_to_rgb": color_name_to_rgb, "_LAMBDA": lambda val: val / 100}
    return eval(t, ns)  # noqa: S307  -- our own recorded reprs, token-checked above


def parameters(tool_name, repr_text):
    short = tool_name.split("__", 1)[1]
    raw = _eval_repr(repr_text)
    schema = {}
    for key, val in raw.items():
        if not isinstance(key, str):
            schema[key] = val  # vol.Any('name','area','floor'), as intent.py:953 writes it
            continue
        mark = MARKS.get((short, key)) or MARKS.get(("*", key))
        if mark is None:
            raise Unmapped("no marker for %s.%s" % (short, key))
        req, desc, default = mark
        kw = {}
        if desc:
            kw["description"] = desc
        if default is not None:
            kw["default"] = default
        schema[(vol.Required if req else vol.Optional)(key, **kw)] = val
    return to_openapi(vol.Schema(schema), custom_serializer=selector_serializer)


def date_fact(stamp):
    return datetime.datetime.fromisoformat(str(stamp)).strftime("date: %Y-%m-%d %a %H:%M")


def labels(member):
    with open(os.path.join(RUNS, "scored", "%s.csv" % member), newline="", encoding="utf-8") as f:
        return {r["task_id"]: r for r in csv.DictReader(f)}


def build(member):
    import yaml
    lab = labels(member)
    files = sorted(f for f in glob.glob(os.path.join(RUNS, member, "*", "report", "*", "*", "*.yaml"))
                   if not f.endswith("_scrape_context.yaml"))
    toolsets, tasks = [], []
    for f in files:
        with open(f, encoding="utf-8") as h:
            d = yaml.safe_load(h)
        ev = {e["event_type"]: e for e in d["context"]["conversation_trace"] if e.get("event_type") != "tool_call"}
        calls = [{"name": e["data"]["tool_name"], "arguments": e["data"]["tool_args"]}
                 for e in d["context"]["conversation_trace"] if e.get("event_type") == "tool_call"]
        det = ev["agent_detail"]["data"]
        system = det["messages"][0]["content"]
        tools = [{"name": t["name"], "parameters": parameters(t["name"], t["parameters"]),
                  **({"description": t["description"]} if t.get("description") else {})} for t in det["tools"]]
        tj = json.dumps(tools)
        if tj not in toolsets:
            toolsets.append(tj)
        t0, t1 = ev["async_process"]["timestamp"], (ev.get("agent_detail") or {}).get("timestamp")
        if "date:" in system or re.search(r"\d{4}-\d{2}-\d{2}", system) or system.lstrip().startswith("{"):
            sys_text = system
        else:
            sys_text = date_fact(t0) + "; " + system
        row = lab.get(d["task_id"], {})
        tasks.append({"task_id": d["task_id"], "category": d["category"], "text": d["task"]["input_text"],
                      "system": sys_text, "toolset": toolsets.index(tj), "recorded_calls": calls,
                      "response": d.get("response"), "label": row.get("label"),
                      "minute_straddle": date_fact(t0) != date_fact(t1) if t1 else None,
                      "expect_changes": d["task"].get("expect_changes")})
    return {"member": member, "toolsets": toolsets, "tasks": tasks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--member", required=True)
    a = ap.parse_args()
    doc = build(a.member)
    out = os.path.join(HERE, "site", "replay_%s.json" % a.member)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    n = len(doc["tasks"])
    print("%s: %d tasks, %d toolsets, %d with recorded calls, %d Good, %d straddle a minute -> %s" % (
        a.member, n, len(doc["toolsets"]), sum(1 for t in doc["tasks"] if t["recorded_calls"]),
        sum(1 for t in doc["tasks"] if t["label"] == "Good"), sum(1 for t in doc["tasks"] if t["minute_straddle"]),
        os.path.relpath(out, HERE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
