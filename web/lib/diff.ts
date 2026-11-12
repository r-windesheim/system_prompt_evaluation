// Word-level diff (LCS) between two responses. Tokens keep their trailing whitespace
// so the rendered text reflows naturally.

export type Op = { kind: "same" | "del" | "ins"; text: string; start: number };

export function tokenize(text: string): { text: string; start: number }[] {
  const out: { text: string; start: number }[] = [];
  const re = /\S+\s*|\s+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) out.push({ text: m[0], start: m.index });
  return out;
}

const norm = (s: string) => s.trim();

/** Ops that turn `a` (with the section) into `b` (without it). `start` indexes into a for same/del and into b for ins. */
export function wordDiff(a: string, b: string): Op[] {
  const A = tokenize(a);
  const B = tokenize(b);
  const n = A.length;
  const m = B.length;
  const L = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      L[i][j] = norm(A[i].text) === norm(B[j].text) ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const ops: Op[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (norm(A[i].text) === norm(B[j].text)) {
      ops.push({ kind: "same", text: A[i].text, start: A[i].start });
      i++;
      j++;
    } else if (L[i + 1][j] >= L[i][j + 1]) {
      ops.push({ kind: "del", text: A[i].text, start: A[i].start });
      i++;
    } else {
      ops.push({ kind: "ins", text: B[j].text, start: B[j].start });
      j++;
    }
  }
  for (; i < n; i++) ops.push({ kind: "del", text: A[i].text, start: A[i].start });
  for (; j < m; j++) ops.push({ kind: "ins", text: B[j].text, start: B[j].start });
  return ops;
}
