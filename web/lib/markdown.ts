// Tiny markdown renderer for model answers, with one detector's spans highlighted as <mark>.
// Escapes everything first; only produces p, ul/ol/li, h4, pre, code, strong, table, mark.

import type { Span } from "./types";

const MS = "\uE000";
const ME = "\uE001";
const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);
const inline = (t: string) => esc(t).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

export function renderAnswer(text: string, spans: Span[], detector: string | null): string {
  const pts: [number, string][] = [];
  for (const s of spans) if (s.detector === detector) pts.push([s.start, MS], [s.end, ME]);
  pts.sort((a, b) => b[0] - a[0] || (a[1] === MS ? -1 : 1));
  let t = text;
  for (const [i, m] of pts) t = t.slice(0, i) + m + t.slice(i);

  let html = "";
  let list: "ul" | "ol" | null = null;
  let code: string[] | null = null;
  let table: string[] = [];
  let open = false;
  const endList = () => {
    if (list) html += `</${list}>`;
    list = null;
  };
  const endTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\s*\|?\s*:?-{2,}/.test(r.replace(/[\uE000\uE001]/g, "")));
    html += "<table>" + rows.map((r, i) => "<tr>" + r.replace(/^\s*\||\|\s*$/g, "").split("|")
      .map((c) => `<${i ? "td" : "th"}>${inline(c.trim())}</${i ? "td" : "th"}>`).join("") + "</tr>").join("") + "</table>";
    table = [];
  };
  for (const raw of t.split("\n")) {
    const o = (raw.match(/\uE000/g) || []).length;
    const c = (raw.match(/\uE001/g) || []).length;
    const now: boolean = open ? o >= c : o > c;
    const line = (open ? MS : "") + raw + (now ? ME : "");
    open = now;
    const bare = line.replace(/[\uE000\uE001]/g, "");
    if (/^\s*```/.test(bare)) {
      if (code) { html += `<pre>${esc(code.join("\n"))}</pre>`; code = null; } else { endList(); endTable(); code = []; }
      continue;
    }
    if (code) { code.push(bare); continue; }
    if (/^\s*\|/.test(bare)) { endList(); table.push(line); continue; }
    endTable();
    const lead = (line.match(/^[\uE000\uE001]*/) || [""])[0];
    const rest = line.slice(lead.length);
    let m: RegExpMatchArray | null;
    if ((m = rest.match(/^\s*#{1,6}\s+(.*)$/))) { endList(); html += `<h4>${inline(lead + m[1])}</h4>`; continue; }
    if ((m = rest.match(/^\s*([-*•]|\d{1,2}[.)])\s+(.*)$/))) {
      const k = /\d/.test(m[1]) ? "ol" : "ul";
      if (list !== k) { endList(); html += `<${k}>`; list = k; }
      html += `<li>${inline(lead + m[2])}</li>`;
      continue;
    }
    if (!bare.trim() || /^\s*(-{3,}|\*{3,})\s*$/.test(bare)) { endList(); continue; }
    endList();
    html += `<p>${inline(line)}</p>`;
  }
  endList();
  endTable();
  if (code) html += `<pre>${esc((code as string[]).join("\n"))}</pre>`;
  return html.replaceAll(MS, "<mark>").replaceAll(ME, "</mark>");
}
