/* Eat Well, Spend Less — required check-in popup on the home page.
 *
 * What this file does:
 *  - opens the popup on a first visit and makes it a proper modal dialog
 *    (page behind it is inert, focus is trapped, Esc / outside-click do nothing)
 *  - when the quiz finishes, closes it and sends the visitor into the page,
 *    personalised for their main challenge
 *  - remembers ONLY "completed + level + theme" on this device for 30 days
 *    (never answers, never anything that leaves the browser)
 *  - fails OPEN: if the quiz can't load, the visitor is let in rather than trapped
 */
(function () {
  "use strict";

  var KEY = "ewsl_gate";
  var TTL = 30 * 24 * 60 * 60 * 1000;
  var html = document.documentElement;
  var gate = document.getElementById("gate");
  var D = window.EWSLQuizData;

  // No gate markup or no quiz data => never block the visitor.
  if (!gate || !D) { html.classList.remove("gate-pending"); return; }

  var behind = Array.prototype.slice.call(document.querySelectorAll("body > header, body > main, body > footer"));
  var isOpen = false;
  var failsafe = null;

  function reduced() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  function track(name, props) {
    try { if (typeof window.plausible === "function") window.plausible(name, props ? { props: props } : undefined); } catch (e) { /* never break the page */ }
  }

  /* ---------------- remembered completion ---------------- */
  function read() {
    try {
      var g = JSON.parse(localStorage.getItem(KEY) || "null");
      if (g && g.v === 1 && Date.now() - g.ts < TTL && D.GATE[g.theme]) return g;
    } catch (e) { /* storage blocked: treat as first visit */ }
    return null;
  }
  function write(rec) { try { localStorage.setItem(KEY, JSON.stringify(rec)); } catch (e) { /* ignore */ } }
  function forget() { try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ } }

  /* ---------------- modal behaviour ---------------- */
  function focusables() {
    var list = gate.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    return Array.prototype.filter.call(list, function (n) {
      return !n.disabled && n.getClientRects().length > 0 && getComputedStyle(n).visibility !== "hidden";
    });
  }
  function onKeydown(e) {
    if (!isOpen) return;
    if (e.key === "Escape") { e.preventDefault(); return; }   // required step: Esc does not dismiss
    if (e.key !== "Tab") return;
    var f = focusables();
    if (!f.length) { e.preventDefault(); gate.focus(); return; }
    var first = f[0], last = f[f.length - 1], a = document.activeElement;
    if (!gate.contains(a)) { e.preventDefault(); first.focus(); return; }
    if (e.shiftKey && a === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && a === last) { e.preventDefault(); first.focus(); }
  }
  function onFocusIn(e) {
    if (isOpen && !gate.contains(e.target)) { var f = focusables(); (f[0] || gate).focus(); }
  }

  function open() {
    // If gate.css failed to load the popup would be an unstyled block inside the page: let the visitor in.
    if (getComputedStyle(gate).position !== "fixed") { html.classList.remove("gate-pending"); return; }
    isOpen = true;
    html.classList.add("gate-pending");
    behind.forEach(function (n) { n.setAttribute("inert", ""); n.setAttribute("aria-hidden", "true"); });
    gate.scrollTop = 0;
    document.addEventListener("keydown", onKeydown, true);
    document.addEventListener("focusin", onFocusIn, true);
    var h = document.getElementById("qz-intro-title");
    (h || gate).focus({ preventScroll: true });
    track("Gate Shown");
    // Fail open: if the quiz script never starts, let the visitor in.
    failsafe = setTimeout(function () { if (!window.__EWSL_QUIZ_READY) failOpen(); }, 6000);
  }

  function close() {
    isOpen = false;
    clearTimeout(failsafe);
    html.classList.remove("gate-pending");
    behind.forEach(function (n) { n.removeAttribute("inert"); n.removeAttribute("aria-hidden"); });
    document.removeEventListener("keydown", onKeydown, true);
    document.removeEventListener("focusin", onFocusIn, true);
  }

  function failOpen() { if (isOpen) close(); }

  // A script that fails to load (or throws before the quiz is ready) must never trap anyone.
  window.addEventListener("error", function (e) {
    var t = e.target;
    var src = (t && t.tagName === "SCRIPT" && t.src) || e.filename || "";
    if (isOpen && !window.__EWSL_QUIZ_READY && /quiz(-data)?\.js/.test(src)) failOpen();
  }, true);

  /* ---------------- personalising the page ---------------- */
  function personalise(rec) {
    var g = D.GATE[rec.theme];
    if (!g) return;
    var strip = document.getElementById("foryou");
    if (strip) {
      document.getElementById("foryou-text").textContent = g.topic + ".";
      var go = document.getElementById("foryou-go");
      go.setAttribute("href", g.target);
      go.innerHTML = "Start with " + g.targetName + " &darr;";
      strip.hidden = false;
    }
    var kicker = document.querySelector(".hero__kicker");
    if (kicker) kicker.textContent = g.heroKicker;
    Array.prototype.forEach.call(document.querySelectorAll("[data-themes]"), function (li) {
      var themes = (li.getAttribute("data-themes") || "").split(" ");
      if (themes.indexOf(rec.theme) < 0 || li.classList.contains("is-foryou")) return;
      li.classList.add("is-foryou");
      var box = li.querySelector("div");
      if (box) {
        var tag = document.createElement("span");
        tag.className = "toc__pick";
        tag.textContent = "Picked for you";
        box.insertBefore(tag, box.firstChild);
      }
    });
  }

  function goTo(selector) {
    var t = document.querySelector(selector);
    if (!t) return;
    t.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" });
    var h = t.querySelector("h2");
    if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
  }

  /** Called by quiz.js when the visitor finishes: close the popup and take them in. */
  function complete(result) {
    var m = D.gateMessage(result);
    var rec = { v: 1, ts: Date.now(), level: m.level, theme: m.theme };
    write(rec);
    close();
    personalise(rec);
    track("Gate Continue", { theme: m.theme });
    // Wait a frame so the page behind is laid out and no longer inert before scrolling.
    requestAnimationFrame(function () { goTo(m.target); });
  }

  window.EWSLGate = { complete: complete };

  /* ---------------- start ---------------- */
  var retake = document.getElementById("foryou-retake");
  if (retake) retake.addEventListener("click", function () { forget(); window.location.reload(); });

  var saved = read();
  if (saved) {
    html.classList.remove("gate-pending");
    personalise(saved);
  } else {
    open();
  }
})();
