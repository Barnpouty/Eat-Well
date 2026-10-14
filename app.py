import json
import os
import re
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
# The single source of truth for every purchase button.
CHECKOUT_URL = "https://checkout.escalepay.com/8372485"

# Optional. Leave unset and the quiz simply says the price is shown at checkout.
# Example: PRODUCT_PRICE="$9.99"
PRODUCT_PRICE = os.environ.get("PRODUCT_PRICE", "").strip()

# Optional. Where optional, consent-based email sign-ups are sent (a JSON POST).
# Works with Zapier / Make / n8n catch-hooks or any endpoint that forwards to
# your email provider. If unset, the email form is not shown at all.
EMAIL_WEBHOOK_URL = os.environ.get("EMAIL_WEBHOOK_URL", "").strip()

# Optional. Privacy-friendly analytics (Plausible). If unset, nothing is tracked.
PLAUSIBLE_DOMAIN = os.environ.get("PLAUSIBLE_DOMAIN", "").strip()

# Optional. The quiz pops up as a required step when someone first opens the home
# page. Set QUIZ_GATE=false to turn the popup off (the quiz stays at /quiz).
QUIZ_GATE = os.environ.get("QUIZ_GATE", "true").strip().lower() not in ("0", "false", "no", "off")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


@app.context_processor
def inject_globals():
    return {
        "checkout_url": CHECKOUT_URL,
        "product_price": PRODUCT_PRICE,
        "email_enabled": bool(EMAIL_WEBHOOK_URL),
        "plausible_domain": PLAUSIBLE_DOMAIN,
        "quiz_gate": QUIZ_GATE,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/quiz")
def quiz():
    return render_template("quiz.html")


@app.post("/api/subscribe")
def subscribe():
    """Optional newsletter / results sign-up. Requires explicit consent."""
    if not EMAIL_WEBHOOK_URL:
        return jsonify(error="not_configured"), 503

    data = request.get_json(silent=True) or {}

    # Honeypot: real visitors never see or fill this field.
    if data.get("website"):
        return jsonify(ok=True)

    email = str(data.get("email", "")).strip()
    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify(error="invalid_email"), 400
    if data.get("consent") is not True:
        return jsonify(error="consent_required"), 400

    payload = {
        "email": email,
        "consent": True,
        "consent_text": str(data.get("consent_text", ""))[:500],
        "source": "grocery-quiz",
        "level": data.get("level") if data.get("level") in (1, 2, 3, 4) else None,
        "score": data.get("score") if isinstance(data.get("score"), int) else None,
        "challenges": [str(c)[:120] for c in (data.get("challenges") or [])][:3],
    }

    req = urllib.request.Request(
        EMAIL_WEBHOOK_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status >= 400:
                raise urllib.error.HTTPError(EMAIL_WEBHOOK_URL, resp.status, "", None, None)
    except (urllib.error.URLError, TimeoutError, OSError):
        return jsonify(error="upstream_failed"), 502

    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True)
