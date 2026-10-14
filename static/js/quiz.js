/* Eat Well, Spend Less — Grocery Budget Check-In (UI) */
(function () {
  "use strict";

  var D = window.EWSLQuizData;
  var root = document.getElementById("quiz");
  if (!D || !root) return;

  var Q = D.QUESTIONS;
  var TOTAL = Q.length;
  var cfg = {
    checkout: root.dataset.checkout,
    price: (root.dataset.price || "").trim(),
    email: root.dataset.email === "true",
    cover: root.dataset.cover,
    home: root.dataset.home || "/",
    mode: root.dataset.mode === "gate" ? "gate" : "page"   // "gate" = required popup on the home page
  };

  function $(id) { return document.getElementById(id); }
  var el = {
    intro: $("qz-intro"), app: $("qz-app"), loading: $("qz-loading"), results: $("qz-results"),
    panel: $("qz-panel"), bubble: $("qz-bubble"), avatar: $("qz-avatar"), loadAvatar: $("qz-loading-avatar"),
    progress: $("qz-progress"), fill: $("qz-progress-fill"), plabel: $("qz-progress-label"),
    back: $("qz-back"), next: $("qz-next"), error: $("qz-error"), step: $("qz-loading-step"),
    tpl: $("tpl-avatar"), start: $("qz-start")
  };

  var state = {
    view: "intro",          // intro | question | review | loading | results
    index: 0,
    answers: new Array(TOTAL).fill(null),
    fromReview: false,
    busy: false,
    advanceTimer: null,
    lastPointer: 0,
    result: null
  };

  /* ---------------- helpers ---------------- */
  function reduced() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
  function icon(name) {
    return '<svg class="icon" aria-hidden="true" focusable="false"><use href="#i-' + name + '"></use></svg>';
  }
  function track(name, props) {
    try {
      if (typeof window.plausible === "function") window.plausible(name, props ? { props: props } : undefined);
    } catch (e) { /* analytics must never break the quiz */ }
  }
  function mountAvatar(container) {
    if (!container || !el.tpl) return;
    container.innerHTML = "";
    container.appendChild(el.tpl.content.cloneNode(true));
  }
  function setBubble(text) {
    el.bubble.textContent = text;
    el.bubble.classList.remove("is-new");
    void el.bubble.offsetWidth; // restart the gentle fade
    el.bubble.classList.add("is-new");
  }
  function cheer() {
    var svg = el.avatar.querySelector("svg");
    if (!svg || reduced()) return;
    svg.classList.remove("is-cheer");
    void svg.getBoundingClientRect();
    svg.classList.add("is-cheer");
  }
  function showError(msg) { el.error.textContent = msg; el.error.hidden = false; }
  function clearError() { el.error.hidden = true; el.error.textContent = ""; }
  function scrollTop() {
    var behavior = reduced() ? "auto" : "smooth";
    if (cfg.mode === "gate") {
      var g = document.getElementById("gate");
      if (g) g.scrollTo({ top: 0, behavior: behavior });
      return;
    }
    window.scrollTo({ top: 0, behavior: behavior });
  }

  function show(view) {
    state.view = view;
    el.intro.hidden = view !== "intro";
    el.app.hidden = !(view === "question" || view === "review");
    el.loading.hidden = view !== "loading";
    el.results.hidden = view !== "results";
  }

  function transition(fn, dir) {
    if (state.busy) return;
    var p = el.panel;
    if (reduced()) { fn(); return; }
    state.busy = true;
    p.style.setProperty("--dir", dir || 1);
    p.classList.add("is-leaving");
    setTimeout(function () {
      try { fn(); } finally {
        p.classList.remove("is-leaving");
        p.classList.add("is-entering");
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            p.classList.remove("is-entering");
            state.busy = false;
          });
        });
      }
    }, 170);
  }

  function setProgress(label, now) {
    el.plabel.textContent = label;
    el.progress.setAttribute("aria-valuenow", String(now));
    el.progress.setAttribute("aria-valuetext", label);
    el.fill.style.width = Math.round((now / TOTAL) * 100) + "%";
  }

  function focusHeading() {
    var h = el.panel.querySelector("[data-focus]");
    if (h) h.focus({ preventScroll: true });
  }

  // After each screen change, make sure the avatar/progress/question are visible
  // (on phones the previous screen may have left the page scrolled further down).
  function ensureInView() {
    if (cfg.mode === "gate") { scrollTop(); return; }
    var nav = document.getElementById("site-nav");
    var offset = (nav ? nav.offsetHeight : 64) + 12;
    var top = el.app.getBoundingClientRect().top;
    if (top < offset - 4 || top > window.innerHeight * 0.5) {
      window.scrollTo({ top: Math.max(0, window.scrollY + top - offset), behavior: reduced() ? "auto" : "smooth" });
    }
  }

  /* ---------------- questions ---------------- */
  function renderQuestion(i) {
    state.view = "question";
    state.index = i;
    show("question");
    var q = Q[i], sel = state.answers[i];
    var html = '<div class="qz-q">' +
      '<p class="qz-q__area">' + q.area + '</p>' +
      '<h2 class="qz-q__title" id="qz-title" tabindex="-1" data-focus>' + q.title + '</h2>' +
      '<div class="qz-options" role="radiogroup" aria-labelledby="qz-title">';
    q.options.forEach(function (o, k) {
      html += '<label class="qz-opt"><input type="radio" name="qz-q' + i + '" value="' + k + '"' +
        (sel === k ? " checked" : "") + '>' +
        '<span class="qz-opt__card"><span class="qz-opt__icon">' + icon(o.icon) + '</span>' +
        '<span class="qz-opt__text">' + o.label + '</span>' +
        '<span class="qz-opt__check">' + icon("tick") + '</span></span></label>';
    });
    html += '</div><p class="qz-hint">Choose the one that fits best. You can change your answer at any time.</p></div>';
    el.panel.innerHTML = html;

    setProgress("Question " + (i + 1) + " of " + TOTAL, i + 1);
    setBubble(sel !== null ? q.after : q.intro);
    clearError();
    updateNav();
    focusHeading();
    ensureInView();
  }

  function updateNav() {
    var answered = state.view === "question" && state.answers[state.index] !== null;
    if (state.view === "question") {
      var last = state.index === TOTAL - 1;
      el.next.textContent = state.fromReview ? "Back to review" : (last ? "Review my answers" : "Next");
      el.next.disabled = !answered;
      el.back.hidden = false;
    } else if (state.view === "review") {
      el.next.textContent = "See my Check-In";
      el.next.disabled = false;
      el.back.hidden = false;
    }
  }

  function selectAnswer(k) {
    var i = state.index;
    var changed = state.answers[i] !== k;
    state.answers[i] = k;
    clearError();
    updateNav();
    if (changed) { setBubble(Q[i].after); cheer(); }
  }

  function scheduleAdvance() {
    clearTimeout(state.advanceTimer);
    state.advanceTimer = setTimeout(function () {
      if (state.view === "question" && state.answers[state.index] !== null) goNext();
    }, reduced() ? 120 : 480);
  }

  function goNext() {
    if (state.busy) return;
    clearTimeout(state.advanceTimer);
    if (state.view === "question") {
      if (state.answers[state.index] === null) {
        showError("Please choose an answer to continue, or tap Back.");
        return;
      }
      if (state.fromReview) { transition(renderReview, 1); return; }
      if (state.index < TOTAL - 1) { transition(function () { renderQuestion(state.index + 1); }, 1); return; }
      transition(renderReview, 1);
    } else if (state.view === "review") {
      submit();
    }
  }

  function goBack() {
    if (state.busy) return;
    clearTimeout(state.advanceTimer);
    if (state.view === "question") {
      if (state.fromReview) { transition(renderReview, -1); return; }
      if (state.index > 0) { transition(function () { renderQuestion(state.index - 1); }, -1); return; }
      show("intro"); scrollTop();
      if (el.start) el.start.focus({ preventScroll: true });
    } else if (state.view === "review") {
      state.fromReview = false;
      transition(function () { renderQuestion(TOTAL - 1); }, -1);
    }
  }

  /* ---------------- review ---------------- */
  function renderReview() {
    state.view = "review";
    state.fromReview = false;
    show("review");
    var html = '<div class="qz-q"><p class="qz-q__area">Almost there</p>' +
      '<h2 class="qz-q__title" id="qz-title" tabindex="-1" data-focus>Take a quick look before we put it together</h2>' +
      '<p class="qz-rev__lead">Everything look right? You can change any answer. Your answers stay on this page and aren\'t sent anywhere.</p>' +
      '<ol class="qz-rev">';
    Q.forEach(function (q, i) {
      var a = state.answers[i];
      html += '<li class="qz-rev__row"><div><p class="qz-rev__q">' + q.short + '</p>' +
        '<p class="qz-rev__a">' + (a === null ? "Not answered yet" : q.options[a].label) + '</p></div>' +
        '<button type="button" class="qz-link" data-edit="' + i + '" aria-label="Change your answer to: ' + q.short + '">Change</button></li>';
    });
    html += '</ol></div>';
    el.panel.innerHTML = html;
    setProgress("Review your answers", TOTAL);
    setBubble("Take your time. Change anything you like.");
    clearError();
    updateNav();
    focusHeading();
    ensureInView();
  }

  /* ---------------- submit + loading ---------------- */
  function submit() {
    if (!D.validateAnswers(state.answers)) {
      var missing = state.answers.indexOf(null);
      if (missing >= 0) {
        state.fromReview = true;
        transition(function () { renderQuestion(missing); showError("Please answer this one before we put the pieces together."); }, -1);
      }
      return;
    }
    var result;
    try { result = D.buildResult(state.answers); }
    catch (e) { showError("Something went wrong putting your results together. Please try again."); return; }
    state.result = result;
    state.view = "loading";
    show("loading");
    mountAvatar(el.loadAvatar);
    scrollTop();

    var steps = ["Looking at your spending…", "Checking your shopping habits…", "Thinking about meal planning…", "Considering food waste…"];
    var gap = reduced() ? 300 : 650, n = 0;
    el.step.textContent = steps[0];
    var timer = setInterval(function () {
      n++;
      if (n < steps.length) el.step.textContent = steps[n];
    }, gap);
    setTimeout(function () {
      clearInterval(timer);
      if (cfg.mode === "gate") renderGateResult(result); else renderResults(result);
    }, gap * steps.length + 200);
  }

  /* ---------------- results ---------------- */
  function areaWord(pct) {
    if (pct < 25) return "In good shape";
    if (pct < 50) return "A little room to grow";
    if (pct < 75) return "Room to grow";
    return "Your biggest opportunity";
  }

  function renderResults(r) {
    track("Quiz Completed", { level: "Level " + r.level.n });
    var lv = r.level;
    var h = "";

    /* summary */
    h += '<section class="res" aria-labelledby="res-title"><div class="res__inner">' +
      '<div class="qz-guide res__guide"><div class="qz-guide__avatar" id="res-avatar" aria-hidden="true"></div>' +
      '<p class="qz-bubble is-new">You did it! Here\'s what I noticed.</p></div>' +
      '<p class="qz-kicker">Your Grocery Budget Check-In</p>' +
      '<h1 class="res__title" id="res-title" tabindex="-1">' + r.headline + '</h1>';

    var segs = "";
    for (var s = 1; s <= 4; s++) segs += '<span class="gauge__seg gauge__seg--' + s + (s === lv.n ? " is-current" : "") + '"></span>';
    var pos = Math.min(98, Math.max(2, r.score));
    h += '<div class="gauge" role="img" aria-label="Your score is ' + r.score + ' out of 100: Level ' + lv.n + ', ' + lv.name +
      '. A higher score means more room to improve.">' +
      '<p class="gauge__scoreline"><span class="gauge__score">' + r.score + '</span><span class="gauge__of"> / 100</span></p>' +
      '<div class="gauge__bar" aria-hidden="true">' + segs +
      '<span class="gauge__marker" data-pos="' + pos + '" style="left:' + (reduced() ? pos : 2) + '%"></span></div>' +
      '<div class="gauge__ticks" aria-hidden="true"><span>Level 1</span><span>Level 2</span><span>Level 3</span><span>Level 4</span></div>' +
      '<p class="gauge__note">A higher score means more room to improve your grocery habits.</p></div>';

    h += '<h2 class="res__level">Level ' + lv.n + ' — ' + lv.name + '</h2>' +
      '<p class="res__lead">' + lv.text + '</p>' +
      '<p>' + r.personal + '</p>' +
      '<aside class="res__disclaimer"><p><strong>An informal self-assessment.</strong> This check-in reflects the habits you told us about. It isn\'t a professional financial evaluation, and it says nothing about your financial worth or your ability to succeed. Grocery costs also depend on things a quiz can\'t see, like household size, where you live and dietary needs.</p></aside>';

    /* areas */
    h += '<h3 class="res__sub">How each area contributed</h3><ul class="areas">';
    D.AREAS.forEach(function (a) {
      var ar = r.areas[a.key];
      h += '<li class="area"><div class="area__row"><span class="area__label">' + a.label + '</span>' +
        '<span class="area__word">' + areaWord(ar.pct) + '</span></div>' +
        '<div class="area__track" aria-hidden="true"><span class="area__fill" data-w="' + Math.round(ar.pct) + '" style="width:' + (reduced() ? Math.round(ar.pct) : 0) + '%"></span></div></li>';
    });
    h += '</ul><p class="res__fine">The four areas count equally toward your score. Answers about your goals aren\'t scored; they just help us personalise your results.</p>';
    h += '</div></section>';

    /* challenges, strengths, actions, support */
    h += '<section class="res res--detail" aria-labelledby="res-challenges"><div class="res__inner">' +
      '<h2 class="res__h2" id="res-challenges">' + (r.polished || lv.n === 1 ? "Where a little polish could help" : "What stood out in your answers") + '</h2>' +
      '<ol class="res__list">';
    r.challenges.forEach(function (c, i) {
      h += '<li><span class="res__num">' + (i + 1) + '</span><div><h3>' + c.title + '</h3><p>' + c.detail + '</p></div></li>';
    });
    h += '</ol>';
    if (r.strengths.length) {
      h += '<h2 class="res__h2 res__h2--sub">What\'s already working</h2><ul class="res__strengths">';
      r.strengths.forEach(function (t) { h += '<li>' + icon("tick") + '<span>' + t + '</span></li>'; });
      h += '</ul>';
    }
    h += '<h2 class="res__h2">Three things to try this week</h2><ol class="res__list res__list--actions">';
    r.actions.forEach(function (a, i) {
      h += '<li><span class="res__num">' + (i + 1) + '</span><div><h3>' + a.title + '</h3><p>' + a.text + '</p></div></li>';
    });
    h += '</ol>' +
      '<div class="res__support"><p class="res__support-title">' + r.supportive + '</p>' +
      '<p>' + r.echo + ' You don\'t need to do everything at once. One small change this week is a real start.</p></div>' +
      '</div></section>';

    /* offer */
    h += '<section class="offer" aria-labelledby="offer-title"><div class="offer__inner">' +
      '<div class="offer__book"><div class="book"><img class="book__cover" src="' + cfg.cover + '" width="896" height="1348" loading="lazy" alt="Eat Well, Spend Less e-book cover by Sharon Inguane and Andile Cossa, showing a pan of pasta with cherry tomatoes and herbs"></div></div>' +
      '<div class="offer__body"><p class="qz-kicker">Eat Well, Spend Less</p>' +
      '<h2 class="offer__title" id="offer-title">Now, let\'s turn your results into a plan.</h2>' +
      '<p>Imagine opening your fridge and knowing what you\'re cooking, what you need to buy, and how to use the ingredients you already have.</p>' +
      '<p>That\'s the idea behind <em>Eat Well, Spend Less</em>: making affordable, satisfying meals easier to plan, shop for, and prepare.</p>' +
      '<p class="offer__why">' + r.why + '</p>' +
      '<ul class="offer__list">';
    r.book.forEach(function (b) {
      h += '<li class="' + (b.startHere ? "is-start" : "") + '">' + icon("tick") + '<div>' +
        (b.startHere ? '<span class="offer__tag">Start here for your results</span>' : (b.forGoal ? '<span class="offer__tag offer__tag--soft">Matches your goal</span>' : "")) +
        '<h3>' + b.title + '</h3><p>' + b.text + '</p></div></li>';
    });
    h += '</ul><div class="offer__ctas">' +
      '<a class="btn btn--primary btn--large" href="' + cfg.checkout + '" target="_blank" rel="noopener" data-checkout="quiz-results">Help Me Eat Well for Less<span class="sr-only"> (opens the secure checkout in a new tab)</span></a>' +
      '<button type="button" class="btn btn--outline btn--large" id="qz-plan-btn" aria-expanded="false" aria-controls="qz-plan">Show Me My First 3 Steps</button></div>' +
      '<p class="offer__terms">' +
      (cfg.price ? 'Price: <strong>' + cfg.price + '</strong>. ' : "") +
      'Checkout opens in a new tab, so your results stay right here. You\'ll see the full price and terms there before you pay. No one can promise exact savings, since they depend on your household, where you shop and what you cook. The book is designed to make the planning part easier.</p>' +
      '<p class="offer__terms">The steps above are yours to keep, whether or not you buy.</p>' +
      '</div></div></section>';

    /* plan (hidden until requested) */
    h += '<section class="plan" id="qz-plan" hidden tabindex="-1" aria-labelledby="plan-title"><div class="plan__inner">' +
      '<h2 id="plan-title">Your first 3 steps</h2>' +
      '<p>Based on your answers, here\'s a gentle way to begin. They\'re free to use, and you can do them with ingredients you already have.</p>' +
      '<ol class="plan__steps">';
    r.plan.forEach(function (s, i) {
      h += '<li><span class="plan__num">' + (i + 1) + '</span><div><p class="plan__when">' + s.when + '</p><p class="plan__text">' + s.text + '</p></div></li>';
    });
    h += '</ol><p class="plan__book">If you\'d like more support with this, the book\'s section on ' + r.planBook.charAt(0).toLowerCase() + r.planBook.slice(1) + ' goes into much more detail.</p></div></section>';

    /* optional email */
    if (cfg.email) {
      h += '<section class="mail" aria-labelledby="mail-title"><div class="mail__inner">' +
        '<h2 id="mail-title">Want a copy of your results?</h2>' +
        '<p>Completely optional. If you\'d like your Check-In results and occasional budget meal-planning tips by email, add your address below. Everything on this page works without it.</p>' +
        '<form id="qz-mail" novalidate>' +
        '<div class="field"><label for="qz-email">Email address</label>' +
        '<input id="qz-email" name="email" type="email" inputmode="email" autocomplete="email" maxlength="254" placeholder="you@example.com"></div>' +
        '<div class="field field--hp" aria-hidden="true"><label>Leave this empty<input type="text" id="qz-hp" name="website" tabindex="-1" autocomplete="off"></label></div>' +
        '<label class="check"><input type="checkbox" id="qz-consent"><span id="qz-consent-text">Yes, please email me my Check-In results and occasional budget meal-planning tips from Eat Well, Spend Less. I can unsubscribe at any time.</span></label>' +
        '<p class="mail__fine">We\'ll only use your email for this. We never ask for bank or card details here.</p>' +
        '<button type="submit" class="btn btn--olive">Send me my results</button>' +
        '<p class="mail__status" id="qz-mail-status" role="status" aria-live="polite"></p></form></div></section>';
    }

    h += '<section class="again"><div class="again__inner">' +
      '<button type="button" class="btn btn--outline" id="qz-restart">Retake the quiz</button>' +
      '<a class="again__link" href="' + cfg.home + '">Back to the main page</a></div></section>';

    el.results.innerHTML = h;
    show("results");
    mountAvatar($("res-avatar"));
    scrollTop();
    var title = $("res-title");
    if (title) title.focus({ preventScroll: true });

    if (!reduced()) {
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          var m = el.results.querySelector(".gauge__marker");
          if (m) m.style.left = m.getAttribute("data-pos") + "%";
          el.results.querySelectorAll(".area__fill").forEach(function (f) { f.style.width = f.getAttribute("data-w") + "%"; });
        });
      });
    }
  }


  /* ---------------- popup closing message (gate mode) ---------------- */
  function renderGateResult(r) {
    var m = D.gateMessage(r);
    track("Quiz Completed", { level: "Level " + r.level.n });
    var first = r.actions[0];
    var h = '<section class="gres" aria-labelledby="gres-title">' +
      '<div class="qz-guide gres__guide"><div class="qz-guide__avatar" id="gres-avatar" aria-hidden="true"></div>' +
      '<p class="qz-bubble is-new">Thank you. Here\'s what I noticed.</p></div>' +
      '<p class="qz-kicker">Your Grocery Budget Check-In</p>' +
      '<h2 class="gres__title" id="gres-title" tabindex="-1">' + m.headline + '</h2>' +
      '<p class="gres__lead">' + m.lead + '</p>' +
      '<p class="gres__body">' + m.body + '</p>' +
      '<ul class="gres__solves">';
    m.solves.forEach(function (x) {
      h += '<li>' + icon("tick") + '<div><h3>' + x.title + '</h3><p>' + x.text + '</p></div></li>';
    });
    h += '</ul>' +
      '<p class="gres__try"><strong>One small thing to try today:</strong> ' + first.title + '. ' + first.text + '</p>' +
      '<div class="gres__bar"><button type="button" class="btn btn--primary btn--large" id="gate-enter">' + m.cta + ' <span aria-hidden="true">&darr;</span></button></div>' +
      '<div class="gres__cta"><p class="gres__fine">This simply takes you into the website. Nothing to buy or sign up for here. ' +
      '<button type="button" class="qz-link" id="gate-review">Change my answers</button></p></div>' +
      '<p class="gres__disclaimer">An informal self-assessment of the habits you reported, not financial advice.</p>' +
      '</section>';
    el.results.innerHTML = h;
    show("results");
    mountAvatar($("gres-avatar"));
    scrollTop();
    var t = $("gres-title");
    if (t) t.focus({ preventScroll: true });
  }

  function togglePlan(btn) {
    var plan = $("qz-plan");
    if (!plan) return;
    var open = plan.hidden;
    plan.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.textContent = open ? "Hide My First 3 Steps" : "Show Me My First 3 Steps";
    if (open) {
      track("Plan Revealed");
      plan.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" });
      plan.focus({ preventScroll: true });
    }
  }

  function restart() {
    clearTimeout(state.advanceTimer);
    state.answers = new Array(TOTAL).fill(null);
    state.fromReview = false;
    state.result = null;
    state.busy = false;
    el.results.innerHTML = "";
    show("question");
    renderQuestion(0);
    scrollTop();
  }

  /* ---------------- optional email ---------------- */
  var EMAIL_RE = /^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$/;
  function submitMail(form) {
    var status = $("qz-mail-status");
    var email = $("qz-email").value.trim();
    var consent = $("qz-consent").checked;
    status.className = "mail__status";
    if (!EMAIL_RE.test(email)) { status.textContent = "Please enter a valid email address."; status.classList.add("is-error"); $("qz-email").focus(); return; }
    if (!consent) { status.textContent = "Please tick the box if you'd like us to email you."; status.classList.add("is-error"); $("qz-consent").focus(); return; }
    var btn = form.querySelector("button[type=submit]");
    btn.disabled = true;
    status.textContent = "Sending…";
    fetch("/api/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: email, consent: true, consent_text: $("qz-consent-text").textContent,
        website: $("qz-hp").value,
        level: state.result.level.n, score: state.result.score,
        challenges: state.result.challenges.map(function (c) { return c.title; })
      })
    }).then(function (res) {
      if (!res.ok) throw new Error("bad status " + res.status);
      status.textContent = "Thank you! We've received your request.";
      status.classList.add("is-ok");
      form.querySelectorAll("input").forEach(function (i) { i.disabled = true; });
      track("Email Signup");
    }).catch(function () {
      status.textContent = "Sorry, that didn't go through. Your results are still here, and you can try again in a moment.";
      status.classList.add("is-error");
      btn.disabled = false;
    });
  }

  /* ---------------- events ---------------- */
  if (el.start) el.start.addEventListener("click", function () {
    track("Quiz Started");
    state.answers = new Array(TOTAL).fill(null);
    state.fromReview = false;
    mountAvatar(el.avatar);
    renderQuestion(0);
    scrollTop();
  });

  el.next.addEventListener("click", goNext);
  el.back.addEventListener("click", goBack);

  el.panel.addEventListener("pointerdown", function () { state.lastPointer = Date.now(); });
  el.panel.addEventListener("keydown", function () { state.lastPointer = 0; });
  el.panel.addEventListener("change", function (e) {
    if (e.target && e.target.type === "radio") selectAnswer(parseInt(e.target.value, 10));
  });
  el.panel.addEventListener("click", function (e) {
    var t = e.target;
    if (t && t.type === "radio") {
      selectAnswer(parseInt(t.value, 10));
      // Auto-advance only for mouse/touch; keyboard users use the Next button.
      // The pointer flag is single-use so it can never leak into a later keyboard action.
      var viaPointer = Date.now() - state.lastPointer < 800;
      state.lastPointer = 0;
      if (viaPointer) scheduleAdvance();
      return;
    }
    var edit = t.closest && t.closest("[data-edit]");
    if (edit) {
      state.fromReview = true;
      var i = parseInt(edit.getAttribute("data-edit"), 10);
      transition(function () { renderQuestion(i); }, -1);
    }
  });

  el.results.addEventListener("click", function (e) {
    var t = e.target;
    var planBtn = t.closest && t.closest("#qz-plan-btn");
    if (planBtn) { togglePlan(planBtn); return; }
    if (t.closest && t.closest("#qz-restart")) restart();
    if (t.closest && t.closest("#gate-enter") && window.EWSLGate && state.result) { window.EWSLGate.complete(state.result); return; }
    if (t.closest && t.closest("#gate-review")) { state.fromReview = false; renderReview(); scrollTop(); }
  });
  el.results.addEventListener("submit", function (e) {
    if (e.target && e.target.id === "qz-mail") { e.preventDefault(); submitMail(e.target); }
  });

  window.__EWSL_QUIZ_READY = true;
})();
