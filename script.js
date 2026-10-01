// ---- Parsing: nodes are {t:'eps'} | {t:'sym',c} | {t:'cat',a,b} | {t:'star',a}
function parse(s) {
  let pos = 0;
  for (let i = 0; i < s.length; i++) {
    if (!"01*()".includes(s[i])) throw new Error(`Illegal character "${s[i]}" at position ${i + 1}. Use only 0, 1, *, ( and ).`);
  }
  const peek = () => (pos < s.length ? s[pos] : null);
  function expr() {
    let node = null;
    while (peek() !== null && peek() !== ")") {
      const t = term();
      node = node === null ? t : { t: "cat", a: node, b: t };
    }
    return node || { t: "eps" };
  }
  function term() {
    let node = atom();
    while (peek() === "*") { pos++; node = { t: "star", a: node }; }
    return node;
  }
  function atom() {
    const c = peek();
    if (c === "0" || c === "1") { pos++; return { t: "sym", c }; }
    if (c === "(") {
      pos++;
      const node = expr();
      if (peek() !== ")") throw new Error("Missing closing parenthesis.");
      pos++;
      return node;
    }
    if (c === "*") throw new Error(`The * at position ${pos + 1} has nothing to repeat.`);
    throw new Error("Unexpected end of expression.");
  }
  const node = expr();
  if (pos !== s.length) throw new Error(`Unmatched ")" at position ${pos + 1}.`);
  return node;
}

// ---- Step 1: does any part match the empty word in 2+ ways?
function epsCount(n) {
  if (n.t === "eps") return 1;
  if (n.t === "sym") return 0;
  if (n.t === "cat") return Math.min(2, epsCount(n.a) * epsCount(n.b));
  return epsCount(n.a) === 0 ? 1 : 2; // star
}
function epsAmbiguous(n) {
  if (epsCount(n) >= 2) return true;
  if (n.t === "cat") return epsAmbiguous(n.a) || epsAmbiguous(n.b);
  if (n.t === "star") return epsAmbiguous(n.a);
  return false;
}

// ---- Step 2: Glushkov automaton. State 0 = start, 1..n = symbol positions.
function glushkov(root) {
  const symbols = [null];
  const follow = {};
  function build(n) { // -> {nullable, first, last}
    if (n.t === "eps") return { nullable: true, first: new Set(), last: new Set() };
    if (n.t === "sym") {
      symbols.push(n.c);
      const i = symbols.length - 1;
      follow[i] = new Set();
      return { nullable: false, first: new Set([i]), last: new Set([i]) };
    }
    if (n.t === "cat") {
      const A = build(n.a), B = build(n.b);
      for (const p of A.last) for (const q of B.first) follow[p].add(q);
      return {
        nullable: A.nullable && B.nullable,
        first: new Set([...A.first, ...(A.nullable ? B.first : [])]),
        last: new Set([...B.last, ...(B.nullable ? A.last : [])]),
      };
    }
    const S = build(n.a); // star
    for (const p of S.last) for (const q of S.first) follow[p].add(q);
    return { nullable: true, first: S.first, last: S.last };
  }
  const R = build(root);
  const delta = symbols.map(() => ({ 0: [], 1: [] }));
  for (const q of R.first) delta[0][symbols[q]].push(q);
  for (const p in follow) for (const q of follow[p]) delta[p][symbols[q]].push(q);
  const finals = new Set(R.last);
  if (R.nullable) finals.add(0);
  return { delta, finals };
}

// ---- Step 3: search the product automaton for two different runs on one word.
function bfs(starts, succ) {
  const parent = new Map(starts.map((s) => [s, null]));
  const queue = [...starts];
  for (let i = 0; i < queue.length; i++) {
    const u = queue[i];
    for (const [lab, v] of succ(u)) {
      if (!parent.has(v)) { parent.set(v, [u, lab]); queue.push(v); }
    }
  }
  return parent;
}
function pathWord(parent, target) {
  const word = [];
  while (parent.get(target) !== null) {
    const [prev, lab] = parent.get(target);
    word.push(lab);
    target = prev;
  }
  return word.reverse().join("");
}

// Returns null if unambiguous, otherwise a word with 2+ parses ("" = empty word).
function findAmbiguity(regex) {
  const root = parse(regex);
  if (epsAmbiguous(root)) return "";
  const { delta, finals } = glushkov(root);
  const key = (p, q) => p + "," + q;
  const split = (k) => k.split(",").map(Number);

  const fwd = (k) => {
    const [p, q] = split(k);
    const out = [];
    for (const a of ["0", "1"])
      for (const p2 of delta[p][a]) for (const q2 of delta[q][a]) out.push([a, key(p2, q2)]);
    return out;
  };
  const reach = bfs([key(0, 0)], fwd);

  const rev = new Map([...reach.keys()].map((k) => [k, []]));
  for (const k of reach.keys()) for (const [, t] of fwd(k)) rev.get(t).push(k);
  const goodFinals = [...reach.keys()].filter((k) => {
    const [p, q] = split(k);
    return finals.has(p) && finals.has(q);
  });
  const coreach = bfs(goodFinals, (k) => rev.get(k).map((u) => ["", u]));

  for (const k of reach.keys()) {
    const [p, q] = split(k);
    if (p !== q && coreach.has(k)) {
      const prefix = pathWord(reach, k);
      const tail = bfs([k], fwd);
      const end = [...tail.keys()].find((s) => {
        const [a, b] = split(s);
        return finals.has(a) && finals.has(b);
      });
      return prefix + pathWord(tail, end);
    }
  }
  return null;
}

// ---- Page wiring (skipped when loaded outside a browser, e.g. in tests)
if (typeof document !== "undefined") {
  const input = document.getElementById("regex");
  const out = document.getElementById("result");

  function run() {
    out.replaceChildren();
    const p = document.createElement("p");
    try {
      const w = findAmbiguity(input.value.trim());
      if (w === null) {
        p.className = "verdict good";
        p.textContent = "Unambiguous";
        out.append(p);
        const d = document.createElement("p");
        d.className = "witness";
        d.textContent = "Every word this regex accepts matches in exactly one way.";
        out.append(d);
      } else {
        p.className = "verdict bad";
        p.textContent = "Ambiguous";
        out.append(p);
        const d = document.createElement("p");
        d.className = "witness";
        if (w === "") {
          d.textContent = "The empty word matches in more than one way (a star repeats something that can match nothing).";
        } else {
          d.append("This word matches in more than one way: ");
          const c = document.createElement("code");
          c.textContent = w;
          d.append(c);
        }
        out.append(d);
      }
    } catch (e) {
      p.className = "error";
      p.textContent = e.message;
      out.append(p);
    }
  }

  document.getElementById("check").addEventListener("click", run);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  document.querySelectorAll(".ex").forEach((b) =>
    b.addEventListener("click", () => { input.value = b.textContent; run(); })
  );
  run();
}

if (typeof module !== "undefined") module.exports = { findAmbiguity, parse };
