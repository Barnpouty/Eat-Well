"""Independent end-to-end audit of the quiz (runs against the snapshot copy only)."""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
SHOTS = "/tmp/audit-shots"
os.makedirs(SHOTS, exist_ok=True)
RECEIVED = []


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        RECEIVED.append(json.loads(self.rfile.read(n) or b"{}"))
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


hook = HTTPServer(("127.0.0.1", 5055), Hook)
threading.Thread(target=hook.serve_forever, daemon=True).start()
os.environ["EMAIL_WEBHOOK_URL"] = "http://127.0.0.1:5055/hook"
os.environ["PRODUCT_PRICE"] = "$9.99"
import app as app_module  # noqa
from werkzeug.serving import make_server  # noqa
srv = make_server("127.0.0.1", 5056, app_module.app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:5056"
CHECKOUT = "https://checkout.escalepay.com/8372485"
from playwright.sync_api import sync_playwright  # noqa

BRIEF = [
    ("How does your grocery spending usually feel by the end of the week?",
     ["I'm usually within my budget.", "I sometimes spend more than I planned.",
      "My money runs out before the week does.", "I honestly don't know where it all goes."]),
    ("What makes eating well on a budget hardest for you?",
     ["Healthy ingredients seem too expensive.", "I buy food but still end up ordering takeout.",
      "I waste food because I don't use everything in time.", "I shop without a clear plan.",
      "All of the above, honestly."]),
    ("When you go grocery shopping, what usually happens?",
     ["I follow a list and stick to it.", "I have a list, but I often buy extra things.",
      "I buy what looks good at the moment.", "I shop several times because I forget what I need."]),
    ("How often do you throw away food you bought but never used?",
     ["Rarely. I use almost everything.", "Sometimes, especially fresh produce.",
      "Often, because I buy more than I need.", "I'm not sure how much I actually waste."]),
    ("What does a typical week of meals look like for you?",
     ["I plan most of my meals ahead.", "I repeat a few meals to save money.",
      "I decide what to eat day by day.", "I often spend extra because I have no plan."]),
    ("Compared with what you intended to spend, how much do you usually go over your grocery budget?",
     ["I rarely go over budget.", "A little extra most weeks.", "Quite a bit, and it adds up.",
      "I don't have a clear grocery budget yet."]),
    ("If you could change one thing about your food budget, what would make the biggest difference?",
     ["Spending less on groceries.", "Eating healthier without paying more.", "Wasting less food.",
      "Having meals planned for the whole week.", "Saving money without feeling deprived."]),
    ("Imagine your groceries were planned, your meals were ready, and less food went to waste. What would that give you?",
     ["More money for other priorities.", "Less stress and more peace of mind.",
      "More time and fewer last-minute meals.", "All three. That's exactly what I need."]),
]
PROFILES = {
    "level1": ([0, 0, 0, 0, 0, 0, 0, 0], 5, 1),
    "level2": ([1, 1, 1, 1, 2, 1, 2, 1], 38, 2),
    "level3": ([3, 3, 3, 3, 2, 3, 1, 0], 62, 3),
    "level4": ([2, 4, 2, 2, 3, 2, 0, 3], 100, 4),
}
LVL = {1: "You're Building Good Habits", 2: "A Few Habits Could Make a Difference",
       3: "Your Budget Needs a Little Structure", 4: "Time for a Fresh Start"}
passed, failed = 0, []


def check(c, m):
    global passed
    if c:
        passed += 1
    else:
        failed.append(m); print("  FAIL:", m)


def new_page(b, w=1280, h=900, reduced=False):
    ctx = b.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce" if reduced else "no-preference")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append("pageerror: %s" % e))
    pg.on("console", lambda m: pg.errors.append("console: " + m.text) if m.type == "error" and "ERR_" not in m.text and "Failed to load resource" not in m.text else None)
    pg.route("**://fonts.*/**", lambda r: r.abort())
    pg.route("**://plausible.io/**", lambda r: r.abort())
    return pg


def label_is(pg, n):
    pg.wait_for_function("t => document.getElementById('qz-progress-label').textContent === t", arg="Question %d of 8" % n, timeout=5000)


def run_through(pg, answers):
    pg.click("#qz-start")
    for i, k in enumerate(answers):
        label_is(pg, i + 1)
        pg.locator(".qz-opt").nth(k).click()
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=5000)


def no_overflow(pg, label):
    w = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    check(w[0] <= w[1] + 1, "%s: horizontal overflow %s" % (label, w))


with sync_playwright() as p:
    br = p.chromium.launch()

    print("1. intro + exact copy")
    pg = new_page(br)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    check(pg.inner_text("h1") == "Your grocery budget shouldn't cost you your peace of mind.", "intro headline")
    body = pg.inner_text("#qz-intro")
    for s in ["Have you ever bought groceries, tried to make your money last, and still wondered where it all went? Or wanted to eat healthier but felt that doing so would cost too much?",
              "You're not alone. And you don't have to figure everything out today.",
              "Take this quick, judgment-free quiz to discover your grocery spending habits and find simple ways to make your money go further, without giving up meals you love.",
              "Let's Find My Savings Potential",
              "Only a few quick questions. No judgment. Just practical steps forward."]:
        check(s in body, "intro copy missing: " + s[:45])
    check(pg.locator(".qz-scene svg").count() >= 1, "intro illustration")
    pg.screenshot(path=SHOTS + "/01-intro-desktop.png")
    no_overflow(pg, "intro desktop")

    print("2. questions, options, navigation")
    pg.click("#qz-start")
    for i, (title, opts) in enumerate(BRIEF):
        label_is(pg, i + 1)
        check(pg.inner_text("#qz-title").strip() == title, "Q%d title" % (i + 1))
        got = [t.strip() for t in pg.locator(".qz-opt__text").all_inner_texts()]
        check(got == opts, "Q%d options: %s" % (i + 1, got))
        check(pg.locator(".qz-opt__icon svg").count() == len(opts), "Q%d icons" % (i + 1))
        check(pg.get_attribute("#qz-progress", "aria-valuenow") == str(i + 1), "Q%d aria progress" % (i + 1))
        check(pg.is_disabled("#qz-next"), "Q%d Next disabled until answered" % (i + 1))
        if i == 0:
            pg.screenshot(path=SHOTS + "/02-question-desktop.png")
        pg.locator(".qz-opt").nth(0).click()
        if i < 7:
            label_is(pg, i + 2)
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=5000)
    check(pg.locator(".qz-rev__row").count() == 8, "review has 8 rows")
    pg.screenshot(path=SHOTS + "/03-review-desktop.png")
    pg.locator("[data-edit='2']").click()
    pg.wait_for_selector("#qz-title:has-text('When you go grocery shopping')")
    check(pg.is_checked(".qz-opt input >> nth=0"), "answer preselected on revisit")
    check(pg.inner_text("#qz-next") == "Back to review", "Next label while editing")
    pg.locator(".qz-opt").nth(2).click()
    pg.wait_for_selector("text=Take a quick look before we put it together", timeout=5000)
    check("I buy what looks good at the moment." in pg.inner_text(".qz-rev"), "edited answer shown in review")
    pg.click("#qz-back")
    pg.wait_for_selector("#qz-title:has-text('Imagine your groceries')")
    check(pg.is_checked(".qz-opt input >> nth=0"), "Q8 answer kept after Back")
    pg.click("#qz-back")
    pg.wait_for_selector("#qz-title:has-text('If you could change one thing')")
    for n in range(6, 0, -1):
        pg.click("#qz-back"); label_is(pg, n)
    pg.click("#qz-back")
    pg.wait_for_selector("#qz-intro:not([hidden])")
    check(True, "Back from Q1 -> intro")

    print("3. keyboard flow")
    pg.click("#qz-start")
    label_is(pg, 1)
    pg.locator(".qz-opt input").nth(1).focus()
    pg.keyboard.press("Space")
    pg.wait_for_timeout(900)
    check(pg.inner_text("#qz-progress-label") == "Question 1 of 8", "Space does not auto-advance")
    check(not pg.is_disabled("#qz-next"), "Next enabled after keyboard select")
    pg.keyboard.press("ArrowDown")
    pg.wait_for_timeout(900)
    check(pg.inner_text("#qz-progress-label") == "Question 1 of 8", "Arrow keys do not auto-advance")
    pg.click("#qz-next")
    label_is(pg, 2)
    check(pg.evaluate("document.activeElement && document.activeElement.id") == "qz-title", "focus moves to heading")
    check(not pg.errors, "console clean: %s" % pg.errors)
    pg.context.close()

    print("4. each result level")
    for name, (ans, score, level) in PROFILES.items():
        pg = new_page(br, reduced=True)
        pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
        run_through(pg, ans)
        pg.click("#qz-next")
        pg.wait_for_selector("text=Let's put the pieces together", timeout=4000)
        pg.wait_for_selector("#res-title", timeout=8000)
        txt = pg.inner_text("#qz-results")
        check(("Level %d — %s" % (level, LVL[level])) in txt, "%s level heading" % name)
        check(pg.inner_text(".gauge__score").strip() == str(score), "%s score %s got %s" % (name, score, pg.inner_text(".gauge__score")))
        check("informal self-assessment" in txt.lower() and "isn't a professional financial evaluation" in txt, "%s disclaimer" % name)
        check(pg.locator(".res__list >> nth=0 >> li").count() in (2, 3), "%s 2-3 challenges" % name)
        check(pg.locator(".res__list--actions li").count() == 3, "%s 3 actions" % name)
        check("Now, let's turn your results into a plan." in txt and "Imagine opening your fridge" in txt, "%s offer copy" % name)
        check(pg.locator(".offer__list li").count() == 6, "%s 6 book items" % name)
        check("$9.99" in pg.inner_text(".offer__terms >> nth=0"), "%s price shown" % name)
        check(pg.locator("a:has-text('Help Me Eat Well for Less')").get_attribute("href") == CHECKOUT, "%s CTA -> checkout" % name)
        check(pg.locator("#qz-plan").is_hidden(), "%s plan hidden at first" % name)
        pg.click("#qz-plan-btn")
        check(pg.locator("#qz-plan").is_visible() and pg.locator(".plan__steps li").count() == 3, "%s plan revealed" % name)
        if name in ("level1", "level4"):
            pg.screenshot(path=SHOTS + "/04-results-%s.png" % name, full_page=True)
        pg.click("#qz-plan-btn")
        check(pg.locator("#qz-plan").is_hidden(), "%s plan toggles closed" % name)
        pg.click("#qz-restart")
        pg.wait_for_selector("#qz-title:has-text('How does your grocery')")
        check(pg.locator(".qz-opt input:checked").count() == 0, "%s restart clears" % name)
        check(not pg.errors, "%s console errors %s" % (name, pg.errors))
        pg.context.close()

    print("5. personalisation differs")
    texts = {}
    for name, ans in {"waste": [0, 2, 0, 2, 0, 0, 2, 1], "plan": [0, 1, 0, 0, 3, 0, 3, 2], "spend": [2, 0, 0, 0, 0, 2, 0, 0]}.items():
        pg = new_page(br, reduced=True)
        pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
        run_through(pg, ans)
        pg.click("#qz-next")
        pg.wait_for_selector("#res-title", timeout=8000)
        texts[name] = (pg.inner_text(".res--detail"), pg.inner_text(".offer__list li >> nth=0"))
        pg.context.close()
    check(len({texts[k][0] for k in texts}) == 3, "challenge/action text differs per visitor")
    check("waste" in texts["waste"][1].lower(), "waste visitor -> waste chapter first: " + texts["waste"][1][:60])
    check("meal plans" in texts["plan"][1].lower(), "planning visitor -> meal plans first: " + texts["plan"][1][:60])

    print("6. optional email")
    pg = new_page(br, reduced=True)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    run_through(pg, PROFILES["level3"][0])
    pg.click("#qz-next")
    pg.wait_for_selector("#qz-mail", timeout=8000)
    check(not pg.locator("#qz-consent").is_checked(), "consent unticked by default")
    check(pg.locator("#res-title").is_visible(), "results visible without email")
    pg.fill("#qz-email", "not-an-email"); pg.check("#qz-consent")
    pg.click("#qz-mail button[type=submit]")
    check("valid email" in pg.inner_text("#qz-mail-status"), "invalid email rejected")
    pg.fill("#qz-email", "friend@example.com"); pg.uncheck("#qz-consent")
    pg.click("#qz-mail button[type=submit]")
    check("tick the box" in pg.inner_text("#qz-mail-status"), "no consent -> blocked")
    check(len(RECEIVED) == 0, "nothing sent without consent")
    pg.check("#qz-consent")
    pg.click("#qz-mail button[type=submit]")
    pg.wait_for_function("document.getElementById('qz-mail-status').textContent.includes('received')", timeout=6000)
    check(len(RECEIVED) == 1 and RECEIVED[0]["email"] == "friend@example.com" and RECEIVED[0]["consent"] is True, "webhook got signup %s" % RECEIVED)
    pg.screenshot(path=SHOTS + "/05-email-done.png")
    pg.context.close()

    print("7. mobile")
    pg = new_page(br, w=390, h=844)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    no_overflow(pg, "intro mobile")
    pg.screenshot(path=SHOTS + "/06-intro-mobile.png", full_page=True)
    pg.click("#qz-start"); pg.wait_for_selector("#qz-title")
    no_overflow(pg, "question mobile")
    pg.screenshot(path=SHOTS + "/07-question-mobile.png")
    hs = pg.evaluate("[...document.querySelectorAll('.qz-opt__card')].map(e => e.getBoundingClientRect().height)")
    check(min(hs) >= 44, "tap targets >=44px (min %s)" % min(hs))
    pg.context.close()
    pg = new_page(br, w=390, h=844, reduced=True)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    run_through(pg, PROFILES["level3"][0])
    pg.click("#qz-next"); pg.wait_for_selector("#res-title", timeout=8000)
    no_overflow(pg, "results mobile")
    pg.click("#qz-plan-btn"); no_overflow(pg, "results mobile + plan")
    pg.screenshot(path=SHOTS + "/08-results-mobile.png", full_page=True)
    pg.context.close()

    print("8. site integration")
    pg = new_page(br)
    app_module.QUIZ_GATE = False      # the required popup replaces the teaser; it has its own suite (e2e_gate.py)
    pg.goto(BASE + "/", wait_until="domcontentloaded")
    check(pg.locator(".quiz-teaser a[href='/quiz']").count() == 1, "teaser -> /quiz")
    check(pg.locator("header nav a[href='/quiz']").count() == 1, "nav -> /quiz")
    check(pg.locator("a.nav__cta").get_attribute("href") == CHECKOUT, "nav CTA -> checkout")
    pg.screenshot(path=SHOTS + "/09-home-teaser.png", full_page=True)
    pg.goto(BASE + "/quiz", wait_until="domcontentloaded")
    check(pg.locator("header nav a[href='/#inside']").count() == 1, "nav anchors work from /quiz")
    pg.context.close()
    br.close()

print("\nchecks passed: %d | failed: %d" % (passed, len(failed)))
for f in failed:
    print(" -", f)
srv.shutdown(); hook.shutdown()
sys.exit(1 if failed else 0)
