"""Backend tests: python3 tests/test_app.py"""
import io, json, os, sys, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as A

passed = 0
def check(c, m):
    global passed
    assert c, m
    passed += 1

sent = []
class FakeResp:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False
def fake_urlopen(req, timeout=0):
    sent.append(json.loads(req.data)); return FakeResp()

c = A.app.test_client()

# pages
for path in ["/", "/quiz"]:
    r = c.get(path); check(r.status_code == 200, path)
html = c.get("/quiz").get_data(as_text=True)
check("peace of mind" in html and "qz-start" in html, "quiz page content")
check('data-checkout="https://checkout.escalepay.com/8372485"' in html, "real checkout URL injected into quiz")
check('data-email="false"' in html, "email disabled when unconfigured")
check("plausible.io" not in html, "no analytics script unless configured")

# unconfigured -> 503, nothing sent
A.EMAIL_WEBHOOK_URL = ""
r = c.post("/api/subscribe", json={"email": "a@b.co", "consent": True}); check(r.status_code == 503, "503 when unconfigured")

# configured
A.EMAIL_WEBHOOK_URL = "https://hooks.example.test/x"
A.urllib.request.urlopen = fake_urlopen
check('data-email="true"' in c.get("/quiz").get_data(as_text=True), "email enabled when configured")

bad = [
    ({}, 400), ({"email": "nope", "consent": True}, 400), ({"email": "a@b", "consent": True}, 400),
    ({"email": "a b@c.com", "consent": True}, 400), ({"email": "a@b.co"}, 400),
    ({"email": "a@b.co", "consent": False}, 400), ({"email": "a@b.co", "consent": "yes"}, 400),
    ({"email": "a@b.co", "consent": 1}, 400), ({"email": ("x" * 250) + "@b.co", "consent": True}, 400),
]
for body, code in bad:
    r = c.post("/api/subscribe", json=body); check(r.status_code == code, f"rejects {str(body)[:40]}")
check(sent == [], "nothing forwarded for invalid requests")
r = c.post("/api/subscribe", data="not json", content_type="text/plain"); check(r.status_code == 400, "non-JSON rejected")

# honeypot: pretends success, forwards nothing
r = c.post("/api/subscribe", json={"email": "bot@b.co", "consent": True, "website": "http://spam"})
check(r.status_code == 200 and sent == [], "honeypot silently dropped")

# happy path; payload is sanitised
r = c.post("/api/subscribe", json={"email": " me@site.com ", "consent": True, "consent_text": "x" * 900,
                                    "level": 3, "score": 62, "challenges": ["a", "b", "c", "d"], "evil": "drop me"})
check(r.status_code == 200 and r.get_json() == {"ok": True}, "success response")
p = sent[0]
check(p["email"] == "me@site.com" and p["consent"] is True and p["level"] == 3 and p["score"] == 62, "payload values")
check(len(p["consent_text"]) == 500 and len(p["challenges"]) == 3 and "evil" not in p, "payload sanitised")
r = c.post("/api/subscribe", json={"email": "me@site.com", "consent": True, "level": 99, "score": "x"})
check(sent[-1]["level"] is None and sent[-1]["score"] is None, "bad level/score discarded")

# upstream failure -> 502
def boom(req, timeout=0): raise urllib.error.URLError("down")
A.urllib.request.urlopen = boom
r = c.post("/api/subscribe", json={"email": "me@site.com", "consent": True}); check(r.status_code == 502, "502 on upstream failure")

# price + analytics config
A.PRODUCT_PRICE = "$9.99"; A.PLAUSIBLE_DOMAIN = "example.com"
h = c.get("/quiz").get_data(as_text=True)
check('data-price="$9.99"' in h and 'data-domain="example.com"' in h, "price + analytics config flow through")
print(f"{passed} backend checks passed")
