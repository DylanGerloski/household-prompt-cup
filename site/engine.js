// Needle in the page: the same four C calls needle's Python wrapper makes (needle/__init__.py, cactus-needle 3.0.x):
// needle_load(weights) once, needle_init(system, tools_json, null) per turn, needle_complete(text, 512, buf, 65536).
// The CI agent built a fresh needle.Needle per request, so every turn here re-inits too: nothing a turn leaves in
// the session can reach the next one. tools may be the exact JSON string Python's json.dumps produced (the replay
// passes that, so Needle reads the same bytes CI gave it) or an array, stringified here.
// The system text gets the wrapper's date fact ("date: YYYY-MM-DD Ddd HH:MM; ") unless it already carries "date:",
// any \d{4}-\d{2}-\d{2} (needle's _ISO_STAMP), or starts with "{" -- _with_date_fact, rule for rule.
const BUF = 65536;
export function dateFact(system, now = new Date()) {
  if (system.includes("date:") || /\d{4}-\d{2}-\d{2}/.test(system)) return system;
  const d = now, p = n => String(n).padStart(2, "0");
  const fact = `date: ${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ` +
    `${["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][d.getDay()]} ${p(d.getHours())}:${p(d.getMinutes())}`;
  if (!system.trim()) return fact;
  if (system.trimStart().startsWith("{")) return system;
  return fact + "; " + system;
}
export async function loadNeedle(base = ".") {
  const M = await createNeedle({ locateFile: f => `${base}/${f}` });
  const cact = new Uint8Array(await (await fetch(`${base}/needle3.cact`)).arrayBuffer());
  const p = M._malloc(cact.length); M.HEAPU8.set(cact, p);
  let rc;  // n is unsigned long long: a BigInt in this build (needle.js uses BigInt), two i32 halves if not
  try { rc = M._needle_load(p, BigInt(cact.length)); } catch (e) { rc = M._needle_load(p, cact.length, 0); }
  if (rc < 0) throw new Error("needle_load failed " + rc);
  const out = M._malloc(BUF);
  return {
    complete(system, tools, text, maxNew = 512) { return JSON.parse(this.completeRaw(system, tools, text, maxNew)); },
    completeRaw(system, tools, text, maxNew = 512) {  // the reply text itself, for score.js's Python-exact keys
      const tj = typeof tools === "string" ? tools : JSON.stringify(tools);
      const r0 = M.ccall("needle_init", "number", ["string", "string", "number"], [dateFact(system || ""), tj, 0]);
      if (r0 < 0) throw new Error("needle_init failed (code " + r0 + "); needle_last_error is not exported by this build");
      const r = M.ccall("needle_complete", "number", ["string", "number", "number", "number"], [text, maxNew, out, BUF]);
      const raw = M.UTF8ToString(out);
      if (r < 0) throw new Error(raw || "needle_complete failed " + r);
      return raw;
    },
  };
}
