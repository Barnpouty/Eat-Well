// Run: node tests/test_quiz_logic.js
const assert = require("assert");
const D = require("../static/js/quiz-data.js");

let checks = 0;
const ok = (c, m) => { checks++; assert.ok(c, m); };
const eq = (a, b, m) => { checks++; assert.deepStrictEqual(a, b, m); };

/* ---- 1. Structure: 8 questions, option counts from the brief ---- */
eq(D.QUESTIONS.length, 8, "8 questions");
eq(D.QUESTIONS.map(q => q.options.length), [4, 5, 4, 4, 4, 4, 5, 4], "option counts");
D.QUESTIONS.forEach(q => q.options.forEach(o => ok(o.label && o.icon, "label+icon")));

/* ---- 2. Independent, hand-calculated expectations ---- */
// answer indexes: [q1..q8]
const cases = [
  // all best habits (Q2 forces a challenge: "healthy ingredients expensive" -> shop 1/5=20%) => 20/4 = 5
  { a: [0, 0, 0, 0, 0, 0, 0, 0], score: 5, level: 1 },
  // all worst, "all of the above" => every area 100%
  { a: [2, 4, 2, 2, 3, 2, 0, 3], score: 100, level: 4 },
  // spend 2/6=33.33, shop 1/5=20, plan 4/5=80, waste 1/5=20 => 38.33 -> 38
  { a: [1, 1, 1, 1, 2, 1, 2, 1], score: 38, level: 2 },
  // spend (2+2)/6=66.67 ; shop (2+2)/5=80; plan (2+... Q2 idx3 plan1 + Q5 idx2 =2... see below
];
// compute case 4 by hand: Q1 idx3 (spend2) Q2 idx3 (shop2 plan1) Q3 idx3 (shop2) Q4 idx3 (waste2) Q5 idx2 (plan2) Q6 idx3 (spend2)
// spend 4/6=66.67 ; shop 4/5=80 ; plan 3/5=60 ; waste 2/5=40 => 246.67/4 = 61.67 -> 62 (level 3)
cases.push({ a: [3, 3, 3, 3, 2, 3, 1, 0], score: 62, level: 3 });
cases.forEach(c => {
  const r = D.scoreAnswers(c.a);
  eq(r.score, c.score, "score for " + c.a);
  eq(r.level.n, c.level, "level for " + c.a);
});

/* ---- 3. Threshold boundaries: every integer 0..100 maps to exactly one level ---- */
const bounds = [[0, 1], [24, 1], [25, 2], [49, 2], [50, 3], [74, 3], [75, 4], [100, 4]];
bounds.forEach(([s, l]) => eq(D.levelFor(s).n, l, "boundary " + s));
for (let s = 0; s <= 100; s++) {
  const matches = D.LEVELS.filter(L => s >= L.min && s <= L.max);
  eq(matches.length, 1, "exactly one level for " + s);
}
eq(D.levelFor(-1), null); eq(D.levelFor(101), null);

/* ---- 4. Validation ---- */
[null, undefined, [], [0, 0, 0], [0, 0, 0, 0, 0, 0, 0, 9], [0, 0, 0, 0, 0, 0, 0, -1],
 [0, 0, 0, 0, 0, 0, 0, 1.5], [0, 0, 0, 0, 0, 0, 0, "1"], [0, 9, 0, 0, 0, 0, 0, 0],
 [0, 0, 0, 0, 0, 0, 0, null], [4, 0, 0, 0, 0, 0, 0, 0]]
  .forEach(bad => { ok(!D.validateAnswers(bad), "rejects " + JSON.stringify(bad)); assert.throws(() => D.scoreAnswers(bad)); checks++; });

/* ---- 5. Exhaustive: every possible combination ---- */
const counts = D.QUESTIONS.map(q => q.options.length);
const total = counts.reduce((a, b) => a * b, 1);
eq(total, 102400, "combination count");
const levelHits = { 1: 0, 2: 0, 3: 0, 4: 0 };
const levelSeen = {};
let min = 1e9, max = -1;
const a = counts.map(() => 0);
let n = 0;
for (;;) {
  const r = D.buildResult(a);
  n++;
  if (!(Number.isInteger(r.score) && r.score >= 0 && r.score <= 100)) throw new Error("bad score " + a);
  if (D.levelFor(r.score) !== r.level) throw new Error("level mismatch " + a);
  levelHits[r.level.n]++;
  min = Math.min(min, r.score); max = Math.max(max, r.score);
  if (!(r.challenges.length >= 2 && r.challenges.length <= 3)) throw new Error("challenges " + a);
  if (r.actions.length !== 3 || new Set(r.actions.map(x => x.key)).size !== 3) throw new Error("actions " + a);
  if (r.plan.length !== 3) throw new Error("plan " + a);
  if (r.book.length !== 6 || new Set(r.book.map(b => b.key)).size !== 6) throw new Error("book " + a);
  if (r.book.filter(b => b.startHere).length !== 2) throw new Error("startHere " + a);
  if (!r.personal || !r.echo || !r.why || !r.headline || !r.supportive) throw new Error("text " + a);
  if (/undefined|NaN|null/.test(r.personal + r.echo + r.why)) throw new Error("bad text " + a + " :: " + r.personal);
  // no shaming vocabulary anywhere in generated copy
  const blob = JSON.stringify(r).toLowerCase();
  if (/\b(irresponsible|failure|careless|lazy|wasteful person|your fault|blame)\b/.test(blob.replace(/not that you're doing anything wrong/g, ""))) throw new Error("tone " + a);
  // emphasis (plan steps / book order) must relate to a challenge the visitor actually sees
  if (!r.challenges.some(c => c.theme === r.primary)) throw new Error("primary theme not among shown challenges " + a);
  if (r.primary === r.secondary) throw new Error("primary==secondary " + a);
  if (r.level.n > 1 && r.personal.indexOf("Your answers suggest") !== -1) throw new Error("repeats level wording " + a);
  // area percentages sane
  Object.values(r.areas).forEach(x => { if (x.pct < 0 || x.pct > 100) throw new Error("pct " + a); });
  levelSeen[r.level.n] = levelSeen[r.level.n] || a.slice();
  // odometer increment
  let i = a.length - 1;
  while (i >= 0 && ++a[i] === counts[i]) { a[i] = 0; i--; }
  if (i < 0) break;
}
eq(n, total, "enumerated all");
console.log("combinations tested:", n, "| score range:", min + "–" + max, "| per level:", JSON.stringify(levelHits));
[1, 2, 3, 4].forEach(l => ok(levelHits[l] > 0, "level " + l + " reachable"));
eq(max, 100, "max score reaches 100");

/* ---- 6. Monotonic: a worse answer (more points) never lowers the score ---- */
// Q1, Q3, Q4, Q5, Q6 are single-area ladders; Q2 vectors aren't ordered so it's excluded.
[0, 2, 3, 4, 5].forEach(qi => {
  const q = D.QUESTIONS[qi];
  const areaKey = Object.keys(q.options.find(o => Object.keys(o.pts).length).pts)[0];
  const sorted = q.options.map((o, i) => ({ i, p: o.pts[areaKey] || 0 })).sort((x, y) => x.p - y.p);
  for (let t = 0; t < 400; t++) {
    const base = counts.map(c => Math.floor(Math.random() * c));
    let prev = -1;
    sorted.forEach(({ i }) => {
      const b = base.slice(); b[qi] = i;
      const s = D.scoreAnswers(b).score;
      ok(s >= prev, "monotonic q" + (qi + 1)); prev = s;
    });
  }
});

/* ---- 7. Q7/Q8 never change the score, only the wording ---- */
for (let t = 0; t < 300; t++) {
  const base = counts.map(c => Math.floor(Math.random() * c));
  const s0 = D.scoreAnswers(base).score;
  for (let g = 0; g < 5; g++) for (let h = 0; h < 4; h++) {
    const b = base.slice(); b[6] = g; b[7] = h;
    ok(D.scoreAnswers(b).score === D.scoreAnswers(Object.assign(base.slice(), { 6: 0, 7: 0 })).score, "q7/q8 unscored");
  }
}

/* ---- 8. Results are genuinely different for different people ---- */
const wasteHeavy = D.buildResult([0, 2, 0, 2, 0, 0, 2, 1]);
const planHeavy = D.buildResult([0, 1, 0, 0, 3, 0, 3, 2]);
const spendHeavy = D.buildResult([2, 0, 0, 0, 0, 2, 0, 0]);
ok(wasteHeavy.challenges[0].key === "waste", "waste-heavy leads with waste");
ok(wasteHeavy.primary === "waste" && wasteHeavy.book[0].key === "waste", "book leads with waste chapter");
ok(planHeavy.primary === "plan" && planHeavy.book[0].key === "plans", "plan-heavy leads with meal plans");
ok(spendHeavy.primary === "spend" && spendHeavy.book[0].key === "shopping", "spend-heavy leads with spending control");
ok(wasteHeavy.personal !== planHeavy.personal && planHeavy.personal !== spendHeavy.personal, "different text");
ok(D.buildResult([0, 0, 0, 0, 0, 0, 0, 0]).strengths.length >= 3, "good habits get recognised");

console.log("assertions passed:", checks);
