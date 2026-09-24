// AT-5: the page's copy of hometiny-run/prompt_carries_no_facts.py, rule for rule, over the names that file read
// (home_names.json, written by build_nofacts.py from its own home_names()). A typed prompt with a SPECIFIC hit is
// refused (exit 1); a hit on a bare domain word only is UNDECIDED (exit 2) and runs with that line printed
// (Architect #19957 item 2, on #13602); 0 runs. The printed
// reason is the Python file's own last line. nofacts_check.html proves the two agree on every case in
// nofacts_cases.json. Python's \w is Unicode, so \w here is [\p{L}\p{N}_] under the u flag; spans are cut in code
// points, as Python slices a str.
export const SPECIFIC = "SPECIFIC", GENERIC_DOMAIN = "GENERIC_DOMAIN";
const W = "[\\p{L}\\p{N}_]";
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const cp = s => Array.from(s);

function hits(text, needles) {
  const found = [], low = text.toLowerCase(), textCp = cp(text);
  for (const [n] of needles) {
    const nl = n.toLowerCase();
    for (const v of new Set([nl, nl.replaceAll("_", " "), nl.replaceAll(" ", "_")])) {
      if (!v.trim()) continue;
      const m = new RegExp(`(?<![\\p{L}\\p{N}_.])${esc(v)}(?!${W})`, "u").exec(low);
      if (!m) continue;
      const start = cp(low.slice(0, m.index)).length, end = start + cp(m[0]).length;
      found.push([n, v, textCp.slice(Math.max(0, start - 20), end + 20).join("")]);
    }
  }
  return found;
}

export function check(text, home) {
  const spec = new Map(home.specific), dom = new Map(home.domain), rows = [];
  const where = (m, n) => [...new Set(m.get(n))].sort().join(",").slice(0, 60);
  for (const [n, , span] of hits(text, home.specific)) rows.push([SPECIFIC, n, where(spec, n), span]);
  for (const [n, , span] of hits(text, home.domain)) {
    if (rows.some(r => r[1] === n && r[0] === SPECIFIC)) continue;
    rows.push([GENERIC_DOMAIN, n, where(dom, n), span]);
  }
  return rows;
}

export function verdict(text, home) {
  const rows = check(text, home);
  const pad = (s, w) => s + " ".repeat(Math.max(0, w - s.length));
  const lines = rows.map(([k, n, w, span]) => `X    ${pad(k, 14)} ${pad(n, 28)} in ${w}   ...${span.trim()}...`);
  const nS = rows.filter(r => r[0] === SPECIFIC).length, nG = rows.length - nS;
  lines.push(`checked 1 prompt(s) against the assist-mini home: ${nS} SPECIFIC hit(s), ${nG} GENERIC_DOMAIN hit(s), ` +
    `${rows.length ? 0 : 1} prompt(s) clear (${rows.length ? "none" : "X"})`);
  let exit = 0;
  if (nS) {
    exit = 1;
    lines.push("FAIL: a prompt carries a name peculiar to this home. Architect #13564 item 2: it is DROPPED " +
      "from the five, not re-worded. This file does not drop it.");
  } else if (nG) {
    exit = 2;
    lines.push("UNDECIDED: the only hits are bare domain words that are also ordinary English. Whether the " +
      "rule reaches them is FORGE's and ARCHITECT's, not this file's and not the dispatcher's. " +
      "Nothing is cleared and nothing is dropped until that is said.");
  } else lines.push("PASS: no prompt carries a device, area or entity name from the home.");
  return { exit, rows, lines, refused: exit === 1 };
}
