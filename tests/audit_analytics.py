import json, os, sys, threading
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
os.environ["PLAUSIBLE_DOMAIN"] = "example.com"; os.environ["EMAIL_WEBHOOK_URL"] = "http://127.0.0.1:5088/x"
import app as A
from werkzeug.serving import make_server
srv = make_server("127.0.0.1", 5089, A.app, threaded=True); threading.Thread(target=srv.serve_forever, daemon=True).start()
from playwright.sync_api import sync_playwright
STUB = "window.__ev=[];window.plausible=function(n,o){window.__ev.push({n:n,p:(o&&o.props)||null})};"
ok = bad = 0
def chk(c, m):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("  FAIL:", m)
html = A.app.test_client().get("/quiz").get_data(as_text=True)
chk('data-domain="example.com"' in html and "plausible.io/js/script.js" in html, "analytics script injected only when configured")
os.environ.pop("PLAUSIBLE_DOMAIN"); A.PLAUSIBLE_DOMAIN = ""
chk("plausible.io" not in A.app.test_client().get("/quiz").get_data(as_text=True), "no analytics script when unconfigured")
with sync_playwright() as p:
    br = p.chromium.launch(); ctx = br.new_context(reduced_motion="reduce"); ctx.add_init_script(STUB); pg = ctx.new_page()
    pg.route("**://fonts.*/**", lambda r: r.abort())
    pg.route("**://checkout.escalepay.com/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<h1>fake checkout</h1>"))
    pg.goto("http://127.0.0.1:5089/quiz", wait_until="domcontentloaded")
    pg.click("#qz-start")
    for i, k in enumerate([3, 3, 3, 3, 2, 3, 1, 0]):
        pg.wait_for_function("t => document.getElementById('qz-progress-label').textContent === t", arg="Question %d of 8" % (i + 1)); pg.locator(".qz-opt").nth(k).click()
    pg.wait_for_selector("text=Take a quick look"); pg.click("#qz-next"); pg.wait_for_selector("#res-title", timeout=8000)
    pg.click("#qz-plan-btn")
    ev = pg.evaluate("window.__ev"); names = [e["n"] for e in ev]
    print("  events:", json.dumps(ev))
    chk("Quiz Started" in names and "Quiz Completed" in names and "Plan Revealed" in names, "start/complete/plan events fire")
    chk(next(e for e in ev if e["n"] == "Quiz Completed")["p"] == {"level": "Level 3"}, "completion event carries only the level")
    chk("answers" not in json.dumps(ev).lower() and "email" not in json.dumps(ev).lower(), "no answers or email in analytics")
    # --- checkout click: event + what happens to the visitor's results ---
    a = pg.locator("a:has-text('Help Me Eat Well for Less')")
    print("  CTA target/rel:", a.get_attribute("target"), a.get_attribute("rel"))
    with ctx.expect_page(timeout=2500) as newp: a.click()
    try: newp.value; opened_new = True
    except Exception: opened_new = False
    ev = pg.evaluate("window.__ev") if not pg.is_closed() else []
    chk(any(e["n"] == "Checkout Click" and e["p"] == {"location": "quiz-results"} for e in ev), "checkout click tracked with location only")
    chk(opened_new, "CTA opens checkout in a NEW tab so the visitor keeps their results")
    br.close()
srv.shutdown()
print("analytics checks passed: %d | failed: %d" % (ok, bad))
