// The page's scorer: the same lookup score_reading.py does (build_labels.case, canon, read_only), in the tab.
// A key is "<task id without its -N repeat suffix>\t<calls as Python's json.dumps(..., sort_keys=True)>", so the
// canonical text is written here byte for byte as Python writes it: ", " and ": " separators, keys sorted, non-ASCII
// as \uXXXX, and a number written as Python would after json.loads read it (a literal with . or e is a float, so 50.0
// stays "50.0"; JavaScript's own JSON.parse would have made it 50). That is why pyKey reads needle's raw text itself.
export const READ_ONLY = "homeassistant__GetLiveContext";
export const caseOf = id => id.replace(/-\d+$/, "");

class Num { constructor(lit) { this.lit = lit; } }

function parse(text) {  // JSON.parse, except numbers stay as their literal text
  let i = 0;
  const ws = () => { while (" \t\n\r".includes(text[i])) i++; };
  const val = () => {
    ws();
    const c = text[i];
    if (c === "{") {
      i++; const o = {}; ws();
      if (text[i] === "}") { i++; return o; }
      for (;;) { ws(); const k = str(); ws(); i++; o[k] = val(); ws(); if (text[i++] === "}") return o; }
    }
    if (c === "[") {
      i++; const a = []; ws();
      if (text[i] === "]") { i++; return a; }
      for (;;) { a.push(val()); ws(); if (text[i++] === "]") return a; }
    }
    if (c === '"') return str();
    for (const [w, v] of [["true", true], ["false", false], ["null", null]]) if (text.startsWith(w, i)) { i += w.length; return v; }
    const m = /^-?\d+(\.\d+)?([eE][+-]?\d+)?/.exec(text.slice(i));
    if (!m) throw new Error("bad JSON at " + i);
    i += m[0].length; return new Num(m[0]);
  };
  const str = () => {
    const m = /^"(?:[^"\\]|\\.)*"/s.exec(text.slice(i));
    i += m[0].length; return JSON.parse(m[0]);
  };
  const v = val(); return v;
}

function pyFloat(lit) {  // repr(float(lit)) for the literals a model writes
  const x = Number(lit);
  if (!Number.isFinite(x)) return x > 0 ? "Infinity" : x < 0 ? "-Infinity" : "NaN";
  let s = String(x);
  if (/e/.test(s)) return s.replace(/e([+-])(\d)$/, "e$10$2");
  if (Math.abs(x) >= 1e16) return x.toExponential().replace(/e([+-])(\d)$/, "e$10$2");
  return /[.]/.test(s) ? s : s + ".0";
}

const pyStr = s => '"' + Array.from(s).map(ch => {
  const c = ch.codePointAt(0);
  if (ch === '"') return '\\"';
  if (ch === "\\") return "\\\\";
  if (ch === "\n") return "\\n"; if (ch === "\r") return "\\r"; if (ch === "\t") return "\\t";
  if (ch === "\b") return "\\b"; if (ch === "\f") return "\\f";
  if (c < 0x20 || (c > 0x7e && c <= 0xffff)) return "\\u" + c.toString(16).padStart(4, "0");
  if (c > 0xffff) { const h = Math.floor((c - 0x10000) / 0x400) + 0xd800, l = (c - 0x10000) % 0x400 + 0xdc00; return "\\u" + h.toString(16) + "\\u" + l.toString(16); }
  return ch;
}).join("") + '"';

export function pyDumps(v) {
  if (v instanceof Num) return /[.eE]/.test(v.lit) ? pyFloat(v.lit) : String(BigInt(v.lit));
  if (v === null) return "null";
  if (v === true) return "true";
  if (v === false) return "false";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : pyFloat(String(v));
  if (typeof v === "string") return pyStr(v);
  if (Array.isArray(v)) return "[" + v.map(pyDumps).join(", ") + "]";
  const ks = Object.keys(v).sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));  // Python sorts str by code point
  return "{" + ks.map(k => pyStr(k) + ": " + pyDumps(v[k])).join(", ") + "}";
}

// needle's raw reply text -> [{name, arguments}] exactly as py_replay.py builds it, numbers kept as literals.
export function callsOf(raw) {
  const r = parse(raw);
  if (!r || r.type !== "call") return [];
  return (r.function_calls || []).map(c => ({ name: c.name, arguments: c.arguments || {} }));
}

export const keyOf = (taskId, calls) =>
  caseOf(taskId) + "\t" + pyDumps(calls.map(c => ({ arguments: c.arguments || {}, name: c.name })));

export function label(labels, taskId, calls) {
  const v = labels[keyOf(taskId, calls)];
  if (v) return v;
  return calls.every(c => c.name === READ_ONLY) ? "Bad" : null;  // null: UNSEEN, no member ever made this call
}
