"""
End-to-end tests for the quiz, run in real Chromium.
Usage:  python3 tests/e2e_quiz.py
Starts the Flask app + a stub email webhook itself; no network needed.
"""
import json, os, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright, expect

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:5057"
CHECKOUT = "https://checkout.escalepay.com/8372485"
SHOTS = os.environ.get("SHOTS", "/tmp/shots")
os.makedirs(SHOTS, exist_ok=True)

# ---------- stub webhook ----------
hooks, hook_mode = [], {"fail": False}
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if hook_mode["fail"]:
            self.send_response(500); self.end_headers(); return
        hooks.append(json.loads(body)); self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def log_message(self, *a): pass
hook_srv = HTTPServer(("127.0.0.1", 9911), H)
threading.Thread(target=hook_srv.serve_forever, daemon=True).start()

env = dict(os.environ, EMAIL_WEBHOOK_URL="http://127.0.0.1:9911/hook", PRODUCT_PRICE="", QUIZ_GATE="false")
srv = subprocess.Popen([sys.executable, "-c",
    "from app import app; app.run(port=5057)"], cwd=ROOT, env=env,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

passed, failed = 0, []
def check(cond, msg):
    global passed
    if cond: passed += 1
    else: failed.append(msg); print("  FAIL:", msg)

STUB = """
window.__events = [];
window.plausible = function(name, opts){ window.__events.push({name:name, props:(opts&&opts.props)||null}); };
"""

def new_page(b, w=1280, h=900, reduced=False):
    ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce" if reduced else "no-preference")
    ctx.add_init_script(STUB)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" and "fonts" not in m.text and "ERR_" not in m.text else None)
    pg.route("**://fonts.*/**", lambda r: r.abort())
    pg.route("https://checkout.escalepay.com/**", lambda r: r.fulfill(status=200, body="<h1>checkout stub</h1>", content_type="text/html"))
    pg.route("https://plausible.io/**", lambda r: r.abort())
    return pg

def start(pg):
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    pg.click("#qz-start")
    pg.wait_for_selector(".qz-q__title")

def answer(pg, idx, via="next"):
    """Pick option idx on the current question and move on using the Next button."""
    pg.locator(".qz-opt").nth(idx).click()
    if via == "next":
        pg.click("#qz-next")
    pg.wait_for_timeout(260)

def do_quiz(pg, answers):
    start(pg)
    for i, a in enumerate(answers):
        pg.wait_for_selector(".qz-q__title")
        t = pg.inner_text("#qz-progress-label") if i < 8 else ""
        pg.locator(".qz-opt").nth(a).click()
        pg.click("#qz-next")
        pg.wait_for_timeout(260)
    pg.wait_for_selector(".qz-rev")

def get_result(pg):
    pg.click("#qz-next")
    pg.wait_for_selector("#res-title", timeout=8000)

with sync_playwright() as p:
    b = p.chromium.launch()

    # =============== 1. intro + navigation basics ===============
    print("1. intro & navigation")
    pg = new_page(b)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    check("peace of mind" in pg.inner_text("#qz-intro-title"), "intro headline")
    check(pg.inner_text("#qz-start") == "Let's Find My Savings Potential", "start CTA text")
    check("No judgment" in pg.inner_text(".qz-reassure"), "reassurance")
    check(pg.locator("#qz-app").is_hidden(), "quiz hidden before start")
    pg.click("#qz-start")
    pg.wait_for_selector(".qz-q__title")
    check(pg.locator("#qz-intro").is_hidden(), "intro hidden after start")
    check(pg.inner_text("#qz-progress-label") == "Question 1 of 8", "progress label Q1")
    check(pg.get_attribute("#qz-progress", "aria-valuenow") == "1", "aria-valuenow Q1")
    check(pg.locator("#qz-next").is_disabled(), "Next disabled until answered")
    check(pg.locator(".qz-opt").count() == 4, "Q1 has 4 options")
    check("grocery spending usually feel" in pg.inner_text(".qz-q__title"), "Q1 text")
    pg.screenshot(path=f"{SHOTS}/q1_desktop.png")
    # validation: Next with nothing chosen shows message (force-click disabled via JS)
    pg.evaluate("document.getElementById('qz-next').disabled=false; document.getElementById('qz-next').click()")
    check(pg.locator("#qz-error").is_visible(), "validation message when unanswered")
    check(pg.inner_text("#qz-progress-label") == "Question 1 of 8", "stays on Q1 when invalid")
    # back from Q1 returns to intro
    pg.click("#qz-back")
    check(pg.locator("#qz-intro").is_visible(), "Back from Q1 returns to intro")
    pg.click("#qz-start")
    pg.wait_for_selector(".qz-q__title")

    # mouse click auto-advances
    pg.locator(".qz-opt").nth(1).click()
    pg.wait_for_function("document.getElementById('qz-progress-label').textContent==='Question 2 of 8'", timeout=3000)
    check(True, "mouse click auto-advances")
    # back keeps the answer
    pg.click("#qz-back"); pg.wait_for_timeout(300)
    check(pg.inner_text("#qz-progress-label") == "Question 1 of 8", "Back goes to Q1")
    check(pg.locator(".qz-opt input").nth(1).is_checked(), "Q1 answer remembered")
    pg.click("#qz-next"); pg.wait_for_timeout(300)

    # rapid double-click on Next must not skip a question
    pg.locator(".qz-opt").nth(0).click()
    pg.click("#qz-next"); pg.click("#qz-next", force=True)
    pg.wait_for_timeout(700)
    check(pg.inner_text("#qz-progress-label") == "Question 3 of 8", "no skipped question on rapid clicks (got %s)" % pg.inner_text("#qz-progress-label"))

    # keyboard: arrows select, no auto-advance, Next works
    pg.locator(".qz-opt input").first.focus()
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(900)
    check(pg.inner_text("#qz-progress-label") == "Question 3 of 8", "keyboard selection does not auto-advance")
    check(pg.locator("#qz-next").is_enabled(), "Next enabled after keyboard selection")
    pg.keyboard.press("Tab")  # moves out of radio group
    pg.focus("#qz-next"); pg.keyboard.press("Enter"); pg.wait_for_timeout(350)
    check(pg.inner_text("#qz-progress-label") == "Question 4 of 8", "Enter on Next advances")
    focused = pg.evaluate("document.activeElement && document.activeElement.id")
    check(focused == "qz-title", "focus moves to question heading (got %s)" % focused)
    check(not pg.errors, "no JS errors in basic flow: %s" % pg.errors)
    pg.close()

    # =============== 2. full flow, review, change, results ===============
    print("2. full flow, review, change answers, results")
    pg = new_page(b)
    answers = [1, 1, 1, 1, 2, 1, 2, 1]
    do_quiz(pg, answers)
    check(pg.locator(".qz-rev__row").count() == 8, "review lists 8 answers")
    check(pg.inner_text("#qz-progress-label") == "Review your answers", "review progress label")
    check(pg.get_attribute("#qz-progress", "aria-valuenow") == "8", "review progress full")
    check(pg.inner_text("#qz-next") == "See my Check-In", "review CTA text")
    pg.screenshot(path=f"{SHOTS}/review_desktop.png")
    # change Q3 from review -> returns to review with new answer
    before = pg.locator(".qz-rev__a").nth(2).inner_text()
    pg.locator("[data-edit='2']").click()
    pg.wait_for_function("document.getElementById('qz-progress-label').textContent==='Question 3 of 8'", timeout=3000)
    check(pg.inner_text("#qz-progress-label") == "Question 3 of 8", "Change opens Q3")
    check(pg.inner_text("#qz-next") == "Back to review", "Next label when editing")
    pg.locator(".qz-opt").nth(0).click()   # auto-advance should return to review
    pg.wait_for_selector(".qz-rev", timeout=3000)
    after = pg.locator(".qz-rev__a").nth(2).inner_text()
    check(before != after and after == "I follow a list and stick to it.", "changed answer shown in review (%s)" % after)
    answers[2] = 0
    # Back from review -> Q8
    pg.click("#qz-back"); pg.wait_for_timeout(350)
    check(pg.inner_text("#qz-progress-label") == "Question 8 of 8", "Back from review -> Q8")
    pg.click("#qz-next"); pg.wait_for_selector(".qz-rev")
    # submit
    pg.click("#qz-next")
    pg.wait_for_selector("#qz-loading:not([hidden])", timeout=2000)
    check("put the pieces together" in pg.inner_text(".qz-loading__title"), "loading message")
    pg.screenshot(path=f"{SHOTS}/loading.png")
    pg.wait_for_selector("#res-title", timeout=8000)
    expected = pg.evaluate("(a)=>{const r=EWSLQuizData.buildResult(a);return {score:r.score,level:r.level.n,name:r.level.name,ch:r.challenges.map(c=>c.title)}}", answers)
    check(pg.inner_text(".gauge__score") == str(expected["score"]), "score shown matches logic (%s)" % expected)
    check(f"Level {expected['level']} — {expected['name']}" in pg.inner_text(".res__level"), "level name shown")
    check(pg.locator(".gauge__marker").count() == 1, "gauge marker")
    check(pg.locator(".area").count() == 4, "4 area bars")
    check("informal self-assessment" in pg.inner_text(".res__disclaimer").lower(), "disclaimer present")
    check("isn't a professional financial evaluation" in pg.inner_text(".res__disclaimer"), "disclaimer wording")
    check(pg.locator(".res__list li").count() >= 5, "challenges + actions listed")
    check(all(t in pg.inner_text("#qz-results") for t in expected["ch"]), "challenges rendered")
    check(pg.inner_text(".offer__title") == "Now, let's turn your results into a plan.", "offer headline")
    check("Imagine opening your fridge" in pg.inner_text(".offer__body"), "offer copy")
    check(pg.locator(".book__cover").count() == 1 and pg.eval_on_selector(".book__cover", "i=>i.complete && i.naturalWidth>0") , "book cover loads")
    check(pg.locator(".offer__list li").count() == 6, "6 e-book content items")
    check(pg.locator(".offer__tag:not(.offer__tag--soft)").count() == 2, "two 'start here' items")
    # primary CTA
    cta = pg.locator("a:has-text('Help Me Eat Well for Less')")
    check(cta.get_attribute("href") == CHECKOUT, "primary CTA href is the real checkout URL")
    # secondary CTA reveals plan
    btn = pg.locator("#qz-plan-btn")
    check(btn.get_attribute("aria-expanded") == "false" and pg.locator("#qz-plan").is_hidden(), "plan hidden initially")
    btn.click(); pg.wait_for_timeout(400)
    check(pg.locator("#qz-plan").is_visible() and btn.get_attribute("aria-expanded") == "true", "plan revealed")
    check(pg.locator(".plan__steps li").count() == 3, "plan has 3 steps")
    pg.screenshot(path=f"{SHOTS}/results_plan.png")
    btn.click()
    check(pg.locator("#qz-plan").is_hidden(), "plan can be hidden again")
    btn.click()
    # checkout opens in a NEW tab so the visitor keeps their results and plan
    check(cta.get_attribute("target") == "_blank" and "noopener" in (cta.get_attribute("rel") or ""), "CTA opens a new tab (noopener)")
    check(cta.get_attribute("href") == CHECKOUT, "CTA href is the real checkout URL")
    with pg.context.expect_page() as newtab:
        cta.click()
    check(pg.locator("#qz-plan-btn").is_visible() and pg.locator("#res-title").is_visible(), "results stay on the original tab")
    newtab.value.close()
    pg.close()

    # =============== 3. analytics events (privacy) ===============
    print("3. analytics")
    pg = new_page(b)
    do_quiz(pg, [0, 2, 0, 2, 0, 0, 2, 1]); get_result(pg)
    pg.click("#qz-plan-btn"); pg.wait_for_timeout(200)
    pg.evaluate("document.querySelectorAll('a[data-checkout]').forEach(a => a.addEventListener('click', e => e.preventDefault()))")
    pg.locator("a:has-text('Help Me Eat Well for Less')").click()
    ev = pg.evaluate("window.__events")
    names = [e["name"] for e in ev]
    check(names[:2] == ["Quiz Started", "Quiz Completed"], "events fired in order: %s" % names)
    check("Plan Revealed" in names and "Checkout Click" in names, "plan + checkout events")
    blob = json.dumps(ev)
    check("@" not in blob and "answers" not in blob.lower(), "no personal data / answers in analytics")
    check([e for e in ev if e["name"] == "Quiz Completed"][0]["props"] == {"level": "Level 2"}, "completion event carries level only")
    pg.close()

    # =============== 4. optional email capture ===============
    print("4. email capture")
    pg = new_page(b)
    do_quiz(pg, [2, 4, 2, 2, 3, 2, 0, 3]); get_result(pg)
    check(pg.locator("#qz-mail").count() == 1, "email form present when configured")
    check(not pg.locator("#qz-consent").is_checked(), "consent box NOT pre-ticked")
    check("unsubscribe" in pg.inner_text("#qz-consent-text").lower(), "consent text explains use")
    pg.fill("#qz-email", "not-an-email"); pg.click("#qz-mail button[type=submit]")
    check("valid email" in pg.inner_text("#qz-mail-status"), "invalid email message")
    pg.fill("#qz-email", "sam@example.com"); pg.click("#qz-mail button[type=submit]")
    check("tick the box" in pg.inner_text("#qz-mail-status"), "consent required message")
    check(len(hooks) == 0, "nothing sent without consent")
    hook_mode["fail"] = True
    pg.check("#qz-consent"); pg.click("#qz-mail button[type=submit]"); pg.wait_for_timeout(800)
    check("didn't go through" in pg.inner_text("#qz-mail-status"), "upstream failure handled gracefully")
    check(pg.locator("#res-title").is_visible() and pg.locator("#qz-mail button[type=submit]").is_enabled(), "results intact + can retry")
    hook_mode["fail"] = False
    pg.click("#qz-mail button[type=submit]"); pg.wait_for_timeout(800)
    check("Thank you" in pg.inner_text("#qz-mail-status"), "success message")
    check(len(hooks) == 1, "one webhook call")
    h = hooks[0]
    check(h["email"] == "sam@example.com" and h["consent"] is True and h["level"] == 4 and h["score"] == 100, "payload: %s" % h)
    check(len(h["challenges"]) in (2, 3) and h["source"] == "grocery-quiz", "payload challenges/source")
    check(set(h) == {"email", "consent", "consent_text", "source", "level", "score", "challenges"}, "payload has no extra data: %s" % sorted(h))
    # honeypot
    pg.close()

    # =============== 5. every level through the UI + score boundaries ===============
    print("5. every level + boundaries through the UI")
    pg = new_page(b)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    targets = [5, 24, 25, 49, 50, 74, 75, 100]
    combos = pg.evaluate("""(targets)=>{
      const Q=EWSLQuizData.QUESTIONS, found={}; const a=Q.map(()=>0);
      for(;;){ const s=EWSLQuizData.scoreAnswers(a).score; if(targets.includes(s)&&!found[s]) found[s]=a.slice();
        let i=a.length-1; while(i>=0 && ++a[i]===Q[i].options.length){a[i]=0;i--;} if(i<0)break; }
      return found; }""", targets)
    check(all(str(t) in combos for t in targets), "found combos for every boundary score")
    exp_level = {5: 1, 24: 1, 25: 2, 49: 2, 50: 3, 74: 3, 75: 4, 100: 4}
    names = {1: "You're Building Good Habits", 2: "A Few Habits Could Make a Difference", 3: "Your Budget Needs a Little Structure", 4: "Time for a Fresh Start"}
    pg.close()
    for t in targets:
        pg = new_page(b)
        do_quiz(pg, combos[str(t)]); get_result(pg)
        shown = int(pg.inner_text(".gauge__score"))
        lvl = pg.inner_text(".res__level")
        check(shown == t, f"score {t} displayed ({shown})")
        check(lvl == f"Level {exp_level[t]} — {names[exp_level[t]]}", f"score {t} -> {lvl}")
        check(pg.locator(".gauge__seg.is-current").get_attribute("class").endswith(f"seg--{exp_level[t]} is-current") or f"seg--{exp_level[t]}" in pg.locator(".gauge__seg.is-current").get_attribute("class"), f"gauge highlights level {exp_level[t]}")
        if t in (5, 24, 25, 50, 75):
            pg.screenshot(path=f"{SHOTS}/results_score{t}.png", full_page=True)
        check(not pg.errors, f"no JS errors at score {t}: {pg.errors}")
        pg.close()

    # =============== 6. restart ===============
    print("6. restart")
    pg = new_page(b)
    do_quiz(pg, [1, 1, 1, 1, 1, 1, 1, 1]); get_result(pg)
    pg.click("#qz-restart"); pg.wait_for_selector(".qz-q__title")
    check(pg.inner_text("#qz-progress-label") == "Question 1 of 8", "restart -> Q1")
    check(not pg.locator(".qz-opt input:checked").count(), "answers cleared after restart")
    check(pg.locator("#qz-results").is_hidden(), "results hidden after restart")
    check(pg.locator("#qz-next").is_disabled(), "Next disabled after restart")
    do_quiz_ans = [0, 0, 0, 0, 0, 0, 0, 0]
    for a in do_quiz_ans:
        pg.locator(".qz-opt").nth(a).click(); pg.click("#qz-next"); pg.wait_for_timeout(260)
    pg.wait_for_selector(".qz-rev"); get_result(pg)
    check(pg.inner_text(".gauge__score") == "5", "second run scores independently")
    pg.close()

    # =============== 7. layout / overflow at common widths ===============
    print("7. responsive checks")
    for w, h in [(320, 640), (390, 844), (768, 1024), (1024, 768), (1440, 900)]:
        pg = new_page(b, w, h)
        pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
        ov = lambda: pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(ov() <= 0, f"intro no horizontal overflow @{w} ({ov()})")
        pg.click("#qz-start"); pg.wait_for_selector(".qz-q__title")
        check(ov() <= 0, f"question no overflow @{w}")
        # touch target sizes
        small = pg.evaluate("[...document.querySelectorAll('.qz-opt__card,#qz-next,#qz-back')].filter(e=>{const r=e.getBoundingClientRect();return r.height<44}).length")
        check(small == 0, f"tap targets >=44px @{w}")
        if w in (320, 390, 768):
            pg.screenshot(path=f"{SHOTS}/q1_{w}.png")
        for i, a in enumerate([2, 4, 2, 2, 3, 2, 1, 3]):
            pg.locator(".qz-opt").nth(a).click()      # tapping auto-advances; wait for it instead of racing it
            if i < 7:
                pg.wait_for_function("t => document.getElementById('qz-progress-label').textContent === t", arg="Question %d of 8" % (i + 2), timeout=6000)
        pg.wait_for_selector(".qz-rev")
        check(ov() <= 0, f"review no overflow @{w}")
        if w in (390,): pg.screenshot(path=f"{SHOTS}/review_{w}.png")
        pg.click("#qz-next"); pg.wait_for_selector("#res-title", timeout=8000)
        pg.wait_for_timeout(1200)
        check(ov() <= 0, f"results no overflow @{w} ({ov()})")
        pg.click("#qz-plan-btn"); pg.wait_for_timeout(300)
        check(ov() <= 0, f"results+plan no overflow @{w}")
        if w in (390, 1440):
            pg.screenshot(path=f"{SHOTS}/results_{w}.png", full_page=True)
        check(not pg.errors, f"no JS errors @{w}: {pg.errors}")
        pg.close()

    # =============== 7b. next question stays in view on phones ===============
    print("7b. scroll position on phones")
    pg = new_page(b, 360, 640)
    start(pg)
    for qi, a in enumerate([3, 4, 3, 3, 3, 3, 4, 3]):
        pg.locator(".qz-opt").nth(a).click()          # last option = lowest on the page
        pg.wait_for_timeout(1300)                     # auto-advance + smooth scroll settle
        pos = pg.evaluate("""()=>{const t=document.querySelector('.qz-q__title').getBoundingClientRect();
                              const n=document.getElementById('site-nav').getBoundingClientRect().bottom;
                              return {top:t.top, nav:n, h:innerHeight}}""")
        check(pos["top"] >= pos["nav"] - 2 and pos["top"] < pos["h"] * 0.7,
              f"after answering Q{qi+1}, next heading is visible below the nav: {pos}")
    pg.close()

    # =============== 8. reduced motion ===============
    print("8. reduced motion")
    pg = new_page(b, reduced=True)
    do_quiz(pg, [2, 4, 2, 2, 3, 2, 0, 3]); get_result(pg)
    left = pg.eval_on_selector(".gauge__marker", "m=>m.style.left")
    check(left == "98%", "gauge placed immediately without animation (%s)" % left)
    w = pg.eval_on_selector(".area__fill", "f=>f.style.width")
    check(w == "100%", "area bars placed immediately (%s)" % w)
    pg.close()

    # =============== 9. mouse auto-advance through whole quiz (no Next clicks) ===============
    print("9. auto-advance flow")
    pg = new_page(b)
    start(pg)
    for a in [0, 1, 2, 3, 0, 1, 2, 3]:
        pg.locator(".qz-opt").nth(a).click()
        pg.wait_for_timeout(950)
    check(pg.locator(".qz-rev").count() == 1, "8 taps lead straight to review")
    pg.close()

    # =============== 10. accessibility (axe) ===============
    print("10. accessibility")
    axe_path = os.path.join(ROOT, "node_modules", "axe-core", "axe.min.js")
    if os.path.exists(axe_path):
        axe = open(axe_path).read()
        def run_axe(pg, label):
            pg.wait_for_timeout(700)  # let fade-in animations finish before measuring contrast
            pg.evaluate(axe)
            res = pg.evaluate("axe.run(document,{runOnly:['wcag2a','wcag2aa','wcag21a','wcag21aa']}).then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,t:v.nodes.slice(0,2).map(n=>n.html.slice(0,120))})))")
            check(not res, f"axe {label}: {json.dumps(res)[:600]}")
        pg = new_page(b)
        pg.goto(BASE + "/quiz", wait_until="domcontentloaded"); run_axe(pg, "intro")
        pg.click("#qz-start"); pg.wait_for_selector(".qz-q__title"); run_axe(pg, "question")
        pg.locator(".qz-opt").nth(0).click(); pg.wait_for_timeout(300); run_axe(pg, "question-selected")
        for a in [1, 1, 1, 1, 1, 0, 0]:
            pg.wait_for_timeout(700); pg.locator(".qz-opt").nth(a).click(); pg.click("#qz-next")
        pg.wait_for_selector(".qz-rev"); run_axe(pg, "review")
        get_result(pg); pg.wait_for_timeout(1300); pg.click("#qz-plan-btn"); pg.wait_for_timeout(300); run_axe(pg, "results")
        pg.close()
    else:
        print("  (axe-core not installed; skipped)")

    # =============== 11. home page integration ===============
    print("11. home page integration")
    pg = new_page(b)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    check(pg.locator(".quiz-teaser a[href='/quiz']").count() == 1, "teaser links to /quiz")
    check(pg.locator(".nav__links a[href='/quiz']").count() == 1, "nav links to /quiz")
    for sel in ["a[data-checkout='hero']", "a[data-checkout='nav']", "a[data-checkout='final-cta']"]:
        check(pg.locator(sel).first.get_attribute("href") == CHECKOUT, f"{sel} -> checkout")
    check(pg.locator(".nav__links a[href='/#inside']").count() == 1, "nav anchors are absolute so they work from /quiz")
    check(not pg.errors, "no JS errors on home: %s" % pg.errors)
    pg.screenshot(path=f"{SHOTS}/home_teaser.png", full_page=True)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    pg.click(".nav__links a[href='/#faq']"); pg.wait_for_url("**/#faq"); 
    check(pg.url.endswith("/#faq"), "nav FAQ link works from the quiz page")
    pg.close()
    b.close()

srv.terminate(); hook_srv.shutdown()
print(f"\n{passed} checks passed, {len(failed)} failed")
if failed:
    for f in failed: print(" -", f)
    sys.exit(1)
