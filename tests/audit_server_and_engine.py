import json, os, re, sys, threading, importlib
from http.server import BaseHTTPRequestHandler, HTTPServer
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
ok = bad = 0
def chk(c, m):
    global ok, bad
    if c: ok += 1
    else: bad += 1; print("  FAIL:", m)

# --- 1. endpoint with NO webhook configured -> form hidden + 503 --------------
os.environ.pop("EMAIL_WEBHOOK_URL", None); os.environ.pop("PRODUCT_PRICE", None)
import app as A
c = A.app.test_client()
page = c.get("/quiz").get_data(as_text=True)
chk('data-email="false"' in page, "email disabled flag when unconfigured")
chk('data-price=""' in page, "no invented price when unset")
chk(c.post("/api/subscribe", json={"email": "a@b.co", "consent": True}).status_code == 503, "503 when not configured")

# --- 2. configured against a stub that can succeed or fail --------------------
mode = {"fail": False}; got = []
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(500 if mode["fail"] else 200); self.end_headers()
    def log_message(self, *a): pass
srv = HTTPServer(("127.0.0.1", 5077), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
A.EMAIL_WEBHOOK_URL = "http://127.0.0.1:5077/x"
c = A.app.test_client()
good = {"email": "Friend@Example.com", "consent": True, "consent_text": "I agree", "level": 3, "score": 62, "challenges": ["a", "b"]}
chk(c.post("/api/subscribe", json=good).status_code == 200 and len(got) == 1, "valid signup forwarded")
chk(got and got[0]["consent"] is True and got[0]["source"] == "grocery-quiz" and got[0]["level"] == 3, "payload shape %s" % got)
for label, body, code in [
    ("bad email", {**good, "email": "nope"}, 400), ("empty email", {**good, "email": ""}, 400),
    ("no consent", {**good, "consent": False}, 400), ("consent as string", {**good, "consent": "true"}, 400),
    ("missing consent", {"email": "a@b.co"}, 400), ("email too long", {**good, "email": "a" * 250 + "@b.co"}, 400)]:
    n = len(got); r = c.post("/api/subscribe", json=body)
    chk(r.status_code == code and len(got) == n, "%s -> %s and nothing forwarded (got %s)" % (label, code, r.status_code))
n = len(got)
chk(c.post("/api/subscribe", json={**good, "website": "http://spam"}).status_code == 200 and len(got) == n, "honeypot silently dropped, not forwarded")
chk(c.post("/api/subscribe", data="email=a@b.co", content_type="application/x-www-form-urlencoded").status_code == 400, "non-JSON body rejected")
chk(c.post("/api/subscribe", data="not json", content_type="application/json").status_code == 400, "malformed JSON rejected")
r = c.post("/api/subscribe", json={**good, "level": 99, "score": "x", "challenges": ["x" * 500] * 9}); 
chk(r.status_code == 200 and got[-1]["level"] is None and got[-1]["score"] is None and len(got[-1]["challenges"]) == 3 and len(got[-1]["challenges"][0]) <= 120, "untrusted fields sanitised")
mode["fail"] = True
chk(c.post("/api/subscribe", json=good).status_code == 502, "upstream 500 -> 502 (UI shows retry message)")
A.EMAIL_WEBHOOK_URL = "http://127.0.0.1:1/unreachable"
chk(c.post("/api/subscribe", json=good).status_code == 502, "unreachable webhook -> 502")
chk(c.get("/api/subscribe").status_code == 405, "GET not allowed")
srv.shutdown()

# --- 3. score boundaries: is each side reachable, and correctly levelled? -----
import subprocess
js = r"""
const D=require('./static/js/quiz-data.js');const c=D.QUESTIONS.map(q=>q.options.length);const a=c.map(()=>0);const seen={};
for(;;){const r=D.scoreAnswers(a);if(!seen[r.score])seen[r.score]=[a.slice(),r.level.n];let i=a.length-1;while(i>=0&&++a[i]===c[i]){a[i]=0;i--}if(i<0)break}
const want=[[24,1],[25,2],[49,2],[50,3],[74,3],[75,4]];
console.log(JSON.stringify(want.map(([s,l])=>({score:s,reachable:!!seen[s],expectLevel:l,gotLevel:seen[s]&&seen[s][1],example:seen[s]&&seen[s][0]})), null, 0));
console.log('distinct scores reachable:',Object.keys(seen).length,'min',Math.min(...Object.keys(seen)),'max',Math.max(...Object.keys(seen)));
"""
out = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True).stdout.strip().split("\n")
for b in json.loads(out[0]):
    chk(b["reachable"] and b["gotLevel"] == b["expectLevel"], "boundary score %s -> level %s (reachable=%s got=%s)" % (b["score"], b["expectLevel"], b["reachable"], b["gotLevel"]))
    print("   boundary", b["score"], "-> L%s via answers %s" % (b["gotLevel"], b["example"]))
print("  ", out[1])

# --- 4. manipulative-pattern scan over everything the quiz can show -----------
files = ["static/js/quiz-data.js", "static/js/quiz.js", "templates/quiz.html", "templates/components/quiz_intro.html", "templates/components/quiz_teaser.html"]
blob = " ".join(open(os.path.join(ROOT, f), encoding="utf-8").read().lower() for f in files)
for w in ["countdown", "hurry", "limited time", "only \\d+ left", "last chance", "expires", "act now", "sold out", "testimonial", "guarantee", "% off", "you will save", "you'll save \\$"]:
    hits = re.findall(w, blob)
    chk(not hits, "manipulative/unsupported phrase present: %s" % w)
chk("no one can promise exact savings" in blob, "explicit no-guarantee statement present")
print("\nserver/engine checks passed: %d | failed: %d" % (ok, bad))
sys.exit(1 if bad else 0)
