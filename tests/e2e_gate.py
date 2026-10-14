"""End-to-end test of the required entry popup (Playwright + Chromium).

Run:  python tests/e2e_gate.py
Starts its own copy of the app; screenshots go to /tmp/gate-shots.
"""
import json, os, sys, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SHOTS = os.environ.get("GATE_SHOTS", "/tmp/gate-shots")
os.makedirs(SHOTS, exist_ok=True)
import app as A  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

PORT = int(os.environ.get("GATE_PORT", "5121"))
srv = make_server("127.0.0.1", PORT, A.app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % PORT
CHECKOUT = "https://checkout.escalepay.com/8372485"
AXE = os.environ.get("AXE_PATH", "/home/claude/eatwell/node_modules/axe-core/axe.min.js")
from playwright.sync_api import sync_playwright  # noqa: E402

PROFILES = {
    "waste": [0, 2, 0, 2, 0, 0, 2, 1],
    "plan": [0, 1, 0, 0, 3, 0, 3, 2],
    "spend": [2, 0, 0, 0, 0, 2, 0, 0],
    "shop": [0, 3, 2, 0, 0, 0, 0, 0],
    "level1": [0, 0, 0, 0, 0, 0, 0, 0],
    "level4": [2, 4, 2, 2, 3, 2, 0, 3],
}
passed, failed = 0, []


def check(c, m):
    global passed
    if c:
        passed += 1
    else:
        failed.append(m); print("  FAIL:", m)


def new_page(br, w=1280, h=900, reduced=True, js=True, stub=False):
    ctx = br.new_context(viewport={"width": w, "height": h}, java_script_enabled=js,
                         reduced_motion="reduce" if reduced else "no-preference")
    if stub:
        ctx.add_init_script("window.__ev=[];window.plausible=function(n,o){window.__ev.push({n:n,p:(o&&o.props)||null})};")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append("pageerror: %s" % e))
    pg.on("console", lambda m: pg.errors.append("console: " + m.text) if m.type == "error" and "ERR_" not in m.text and "Failed to load resource" not in m.text else None)
    pg.route("**://fonts.*/**", lambda r: r.abort())
    pg.route("**://plausible.io/**", lambda r: r.abort())
    return pg


def label_is(pg, n):
    pg.wait_for_function("t => document.getElementById('qz-progress-label').textContent === t", arg="Question %d of 8" % n, timeout=6000)


def take_quiz(pg, answers):
    pg.click("#qz-start")
    for i, k in enumerate(answers):
        label_is(pg, i + 1)
        pg.locator(".qz-opt").nth(k).click()
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=6000)
    pg.click("#qz-next")
    pg.wait_for_selector("#gres-title", timeout=9000)


def expected(pg, ans):
    return pg.evaluate("a => { const D = window.EWSLQuizData; return D.gateMessage(D.buildResult(a)); }", ans)


def gate_visible(pg):
    return pg.locator("#gate").is_visible()


def axe(pg, label):
    pg.add_script_tag(path=AXE)
    r = pg.evaluate("axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']}}).then(r=>r.violations.map(v=>v.id+' x'+v.nodes.length+' '+v.nodes[0].target.join(' ')))")
    check(not r, "axe %s: %s" % (label, r))


with sync_playwright() as p:
    br = p.chromium.launch()

    # ============ 1. first visit: a real, required modal =================
    print("1. first visit shows a mandatory modal")
    pg = new_page(br)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    check(gate_visible(pg), "gate visible on first visit")
    check(pg.evaluate("document.documentElement.classList.contains('gate-pending')"), "gate-pending flag set before paint")
    d = pg.locator("#gate")
    check(d.get_attribute("role") == "dialog" and d.get_attribute("aria-modal") == "true", "role=dialog aria-modal")
    check(all(pg.evaluate("s => document.querySelector(s).hasAttribute('inert')", s) for s in ("body > header", "body > main", "body > footer")), "page behind is inert")
    check(pg.evaluate("getComputedStyle(document.body).overflow") == "hidden", "page scroll locked")
    check(pg.evaluate("document.querySelector('#qz-intro-title').tagName") == "H2", "popup heading is h2 (no second h1)")
    check(pg.locator("#gate button[aria-label*='lose'], #gate .gate__close, #gate [data-dismiss]").count() == 0, "no close/skip control")
    txt = pg.inner_text("#gate")
    for s in ["Your grocery budget shouldn't cost you your peace of mind.", "Let's Find My Savings Potential",
              "Only a few quick questions. No judgment. Just practical steps forward."]:
        check(s in txt, "gate copy: " + s[:40])
    pg.screenshot(path=SHOTS + "/01-gate-intro-desktop.png")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
    check(gate_visible(pg), "Esc does not dismiss")
    pg.mouse.click(4, 4); pg.wait_for_timeout(150)
    check(gate_visible(pg), "clicking outside does not dismiss")
    ok = True
    for _ in range(14):
        pg.keyboard.press("Tab")
        ok &= pg.evaluate("!!document.activeElement.closest('#gate')")
    check(ok, "Tab never leaves the dialog")
    ok = True
    for _ in range(6):
        pg.keyboard.press("Shift+Tab")
        ok &= pg.evaluate("!!document.activeElement.closest('#gate')")
    check(ok, "Shift+Tab never leaves the dialog")
    pg.evaluate("document.querySelector('.hero__actions a').focus()")
    check(pg.evaluate("!!document.activeElement.closest('#gate')"), "cannot focus page content behind the dialog")
    axe(pg, "gate intro")
    check(not pg.errors, "console clean: %s" % pg.errors)
    pg.context.close()

    # ============ 2. each theme: tailored message -> into the site ========
    print("2. themed messages")
    seen_headlines = {}
    for name, ans in PROFILES.items():
        pg = new_page(br, stub=True)
        pg.goto(BASE + "/", wait_until="domcontentloaded")
        take_quiz(pg, ans)
        m = expected(pg, ans)
        seen_headlines[name] = pg.inner_text("#gres-title")
        check(pg.inner_text("#gres-title") == m["headline"], "%s headline" % name)
        check(m["lead"] in pg.inner_text(".gres__lead"), "%s lead" % name)
        check(pg.locator(".gres__solves li").count() == 3, "%s: 3 'how the book solves it' points" % name)
        check(m["cta"] in pg.inner_text("#gate-enter"), "%s CTA label" % name)
        vb = pg.evaluate("(()=>{const r=document.getElementById('gate-enter').getBoundingClientRect();return [r.top, r.bottom, innerHeight]})()")
        check(vb[0] >= 0 and vb[1] <= vb[2], "%s: main button visible without scrolling (%s)" % (name, vb))
        check(pg.locator("#gate a[href*='checkout']").count() == 0, "%s: no checkout link/pressure inside the popup" % name)
        check("Nothing to buy" in pg.inner_text(".gres__fine"), "%s: says nothing to buy" % name)
        check("informal self-assessment" in pg.inner_text(".gres__disclaimer"), "%s disclaimer" % name)
        check(not any(w in pg.inner_text("#gate").lower() for w in ("guarantee", "limited time", "countdown", "only today")), "%s: no pressure language" % name)
        if name in ("waste", "level1"):
            pg.screenshot(path=SHOTS + "/02-gate-message-%s.png" % name)
        pg.click("#gate-enter")
        pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')", timeout=3000)
        check(not gate_visible(pg), "%s: popup closed" % name)
        check(not any(pg.evaluate("s => document.querySelector(s).hasAttribute('inert')", s) for s in ("body > header", "body > main", "body > footer")), "%s: page usable again" % name)
        check(pg.evaluate("getComputedStyle(document.body).overflow") != "hidden", "%s: scroll unlocked" % name)
        check(pg.locator("#foryou").is_visible() and m["topic"] in pg.inner_text("#foryou"), "%s: 'picked for you' strip" % name)
        check(pg.inner_text(".hero__kicker") == m["heroKicker"], "%s: hero retargeted" % name)
        picks = pg.locator(".toc__item.is-foryou").count()
        check(picks >= 1 and pg.locator(".toc__pick").count() == picks, "%s: %d chapters highlighted" % (name, picks))
        pg.wait_for_timeout(300)
        top = pg.evaluate("s => document.querySelector(s).getBoundingClientRect().top", m["target"])
        check(-30 <= top <= 140, "%s: scrolled to %s (top=%s)" % (name, m["target"], top))
        check(pg.evaluate("document.activeElement && document.activeElement.closest('%s') !== null" % m["target"]), "%s: focus moved to target section" % name)
        stored = json.loads(pg.evaluate("localStorage.getItem('ewsl_gate')"))
        check(sorted(stored) == ["level", "theme", "ts", "v"], "%s: only level/theme stored: %s" % (name, sorted(stored)))
        ev = [e["n"] for e in pg.evaluate("window.__ev")]
        check(all(x in ev for x in ("Gate Shown", "Quiz Started", "Quiz Completed", "Gate Continue")), "%s: analytics events %s" % (name, ev))
        check("answers" not in json.dumps(pg.evaluate("window.__ev")).lower(), "%s: analytics carry no answers" % name)
        check(pg.locator("a.nav__cta").get_attribute("href") == CHECKOUT, "%s: nav checkout intact" % name)
        if name == "waste":
            pg.screenshot(path=SHOTS + "/03-home-personalised-waste.png")
            axe(pg, "personalised home")
        check(not pg.errors, "%s console: %s" % (name, pg.errors))
        pg.context.close()
    check(len({seen_headlines[k] for k in ("waste", "plan", "spend", "shop")}) == 4, "the four themes show four different messages")

    # ============ 3. remembered, retake, expiry ==========================
    print("3. repeat visits")
    pg = new_page(br)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    take_quiz(pg, PROFILES["plan"]); pg.click("#gate-enter")
    pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')")
    pg.reload(wait_until="domcontentloaded")
    check(not pg.evaluate("document.documentElement.classList.contains('gate-pending')"), "no popup on return visit (no flash: flag never set)")
    check(not gate_visible(pg) and pg.locator("#foryou").is_visible(), "returning visitor sees personalised page")
    pg.click("#foryou-retake")
    pg.wait_for_selector("#gate", state="visible", timeout=4000)
    check(gate_visible(pg) and pg.evaluate("localStorage.getItem('ewsl_gate')") is None, "Retake clears flag and reopens the quiz")
    take_quiz(pg, PROFILES["spend"]); pg.click("#gate-enter")
    pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')")
    pg.evaluate("localStorage.setItem('ewsl_gate', JSON.stringify({v:1, ts: Date.now() - 31*24*3600*1000, level:2, theme:'plan'}))")
    pg.reload(wait_until="domcontentloaded")
    check(gate_visible(pg), "completion expires after 30 days")
    pg.evaluate("localStorage.setItem('ewsl_gate', 'garbage{')")
    pg.reload(wait_until="domcontentloaded")
    check(gate_visible(pg), "corrupt stored value => treated as first visit, no crash")
    # change answers from the closing message
    take_quiz(pg, PROFILES["waste"])
    pg.click("#gate-review")
    pg.wait_for_selector("text=Take a quick look before we put it together")
    pg.locator("[data-edit='1']").click()
    pg.wait_for_selector("#qz-title:has-text('What makes eating well')")
    pg.locator(".qz-opt").nth(3).click()
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=4000)
    pg.click("#qz-next"); pg.wait_for_selector("#gres-title", timeout=9000)
    check(gate_visible(pg), "can change answers from the closing message and get a new one")
    check(not pg.errors, "console clean: %s" % pg.errors)
    pg.context.close()

    # ============ 4. nobody gets trapped =================================
    print("4. fail-open and switches")
    pg = new_page(br)
    pg.route("**/static/js/quiz.js", lambda r: r.abort())
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')", timeout=9000)
    check(not gate_visible(pg) and pg.locator("main").get_attribute("inert") is None, "quiz.js blocked => visitor let in, page usable")
    pg.context.close()
    pg = new_page(br)
    pg.route("**/static/js/quiz-data.js", lambda r: r.abort())
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.wait_for_timeout(500)
    check(not gate_visible(pg) and pg.locator("main").get_attribute("inert") is None, "quiz-data.js blocked => visitor let in")
    pg.context.close()
    pg = new_page(br)
    pg.route("**/static/css/gate.css", lambda r: r.abort())
    pg.goto(BASE + "/", wait_until="load")
    pg.wait_for_timeout(400)
    check(not gate_visible(pg) and pg.locator("main").get_attribute("inert") is None, "gate.css blocked => visitor let in, no unstyled popup")
    pg.context.close()
    pg = new_page(br, js=False)
    pg.goto(BASE + "/", wait_until="load")
    check(not gate_visible(pg) and pg.locator("h1.hero__headline").is_visible(), "no JavaScript => normal site, no popup")
    pg.context.close()
    A.QUIZ_GATE = False
    pg = new_page(br)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    check(pg.locator("#gate").count() == 0 and not pg.evaluate("document.documentElement.classList.contains('gate-pending')"), "QUIZ_GATE=false removes the popup entirely")
    check(pg.locator(".quiz-teaser a[href='/quiz']").count() == 1, "teaser returns when the popup is off")
    pg.context.close()
    A.QUIZ_GATE = True
    pg = new_page(br)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    check(pg.locator("#gate").count() == 0 and pg.locator("#qz-intro").is_visible(), "/quiz page is a normal page, not gated")
    pg.context.close()

    # ============ 5. keyboard only =======================================
    print("5. keyboard-only run")
    pg = new_page(br)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    check(pg.evaluate("document.activeElement.id") == "qz-intro-title", "focus starts on the popup heading")
    pg.keyboard.press("Tab"); check(pg.evaluate("document.activeElement.id") == "qz-start", "Tab reaches Start")
    pg.keyboard.press("Enter")
    for i in range(8):
        label_is(pg, i + 1)
        pg.locator(".qz-opt input").nth(1).focus(); pg.keyboard.press("Space")
        pg.click("#qz-next") if False else pg.focus("#qz-next"); pg.keyboard.press("Enter")
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=5000)
    pg.focus("#qz-next"); pg.keyboard.press("Enter")
    pg.wait_for_selector("#gres-title", timeout=9000)
    check(pg.evaluate("document.activeElement.id") == "gres-title", "focus lands on the result heading")
    pg.focus("#gate-enter"); pg.keyboard.press("Enter")
    pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')", timeout=3000)
    check(not gate_visible(pg), "entire flow completable with keyboard alone")
    pg.context.close()

    # ============ 6. phones ==============================================
    print("6. phone layout")
    pg = new_page(br, w=390, h=844)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    ov = lambda: pg.evaluate("[document.getElementById('gate').scrollWidth, document.getElementById('gate').clientWidth]")
    o = ov(); check(o[0] <= o[1] + 1, "gate intro: no sideways scroll %s" % o)
    box = pg.evaluate("(()=>{const r=document.querySelector('.gate__panel').getBoundingClientRect();return [r.width, r.left]})()")
    check(box[0] >= 389 and box[1] == 0, "popup is a full-width sheet on phones %s" % box)
    pg.screenshot(path=SHOTS + "/04-gate-intro-mobile.png")
    pg.click("#qz-start"); pg.wait_for_selector("#qz-title")
    o = ov(); check(o[0] <= o[1] + 1, "gate question: no sideways scroll %s" % o)
    hs = pg.evaluate("[...document.querySelectorAll('.qz-opt__card')].map(e=>e.getBoundingClientRect().height)")
    check(min(hs) >= 44, "tap targets >= 44px (min %s)" % min(hs))
    pg.screenshot(path=SHOTS + "/05-gate-question-mobile.png")
    pg.context.close()
    pg = new_page(br, w=390, h=844)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    take_quiz(pg, PROFILES["spend"])
    o = ov(); check(o[0] <= o[1] + 1, "gate message: no sideways scroll %s" % o)
    vb = pg.evaluate("(()=>{const r=document.getElementById('gate-enter').getBoundingClientRect();return [r.top, r.bottom, innerHeight]})()")
    check(vb[0] >= 0 and vb[1] <= vb[2], "phone: main button visible without scrolling %s" % vb)
    pg.screenshot(path=SHOTS + "/06-gate-message-mobile.png", full_page=False)
    axe(pg, "gate message mobile")
    pg.click("#gate-enter")
    pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')")
    pg.wait_for_timeout(300)
    w = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(w[0] <= w[1] + 1, "personalised home on phone: no sideways scroll %s" % w)
    pg.evaluate("window.scrollTo(0,0)")
    pg.screenshot(path=SHOTS + "/07-home-personalised-mobile.png")
    pg.context.close()

    pg = new_page(br, w=1366, h=640)          # short laptop screen
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    take_quiz(pg, PROFILES["waste"])
    vb = pg.evaluate("(()=>{const r=document.getElementById('gate-enter').getBoundingClientRect();return [r.top, r.bottom, innerHeight]})()")
    check(vb[0] >= 0 and vb[1] <= vb[2], "short laptop: main button visible without scrolling %s" % vb)
    pg.context.close()

    # ============ 7. with real motion (not reduced) ======================
    print("7. animated run")
    pg = new_page(br, reduced=False)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    pg.click("#qz-start")
    for i, k in enumerate(PROFILES["waste"]):
        label_is(pg, i + 1); pg.locator(".qz-opt").nth(k).click()
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=6000)
    pg.click("#qz-next")
    pg.wait_for_selector("text=Let's put the pieces together", timeout=3000)
    pg.wait_for_selector("#gres-title", timeout=9000)
    pg.click("#gate-enter")
    pg.wait_for_function("!document.documentElement.classList.contains('gate-pending')", timeout=3000)
    check(not pg.errors, "animated run console clean: %s" % pg.errors)
    pg.context.close()
    br.close()

print("\ngate checks passed: %d | failed: %d" % (passed, len(failed)))
for f in failed:
    print(" -", f)
srv.shutdown()
sys.exit(1 if failed else 0)
