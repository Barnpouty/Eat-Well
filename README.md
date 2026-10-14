# Eat Well, Spend Less — website

A Flask sales page for the "Eat Well, Spend Less" e-book by Sharon Inguane & Andile Cossa.

## Run locally

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## Structure

```
eatwell/
├── app.py                  # Flask app
├── requirements.txt
├── templates/
│   ├── base.html
│   ├── index.html
│   └── components/         # navbar, hero, problem, inside (TOC), recipes,
│                            # budget/ledger, audience, authors, faq, final_cta, footer
└── static/
    ├── css/style.css
    ├── js/main.js
    └── images/cover.jpg    # cropped from the supplied e-book cover
```

## Checkout

All purchase buttons link to the checkout URL set as `CHECKOUT_URL` in `app.py`
(currently `https://checkout.escalepay.com/8372485`) and injected into every
template via a Flask context processor — update it in one place if it ever changes.

## Deploy to Vercel

This repo is already set up for Vercel via `vercel.json` and `api/index.py`
(a thin wrapper that re-exports the Flask `app` object — Vercel's Python
runtime runs it as a serverless function per request).

### 1. Push it to GitHub

```
cd eatwell
git init
git add .
git commit -m "Eat Well, Spend Less site"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

### 2. Deploy

**Option A — Vercel dashboard (no CLI):**
1. Go to vercel.com → Add New → Project.
2. Import the GitHub repo you just pushed.
3. Vercel will detect `vercel.json` automatically. Leave the framework
   preset as "Other" and click Deploy.
4. You'll get a live URL like `eatwell-yourname.vercel.app` within a minute.

**Option B — Vercel CLI:**
```
npm install -g vercel
cd eatwell
vercel login
vercel          # deploys a preview
vercel --prod   # promotes to production
```

### 3. Connect your custom domain

1. In the Vercel dashboard, open your project → **Settings → Domains**.
2. Type your domain (e.g. `eatwellspendless.com`) and click **Add**.
3. Vercel will show you the exact DNS records to create. Typically:
   - **Root domain** (`eatwellspendless.com`): an **A** record pointing to
     `76.76.21.21`
   - **www subdomain** (`www.eatwellspendless.com`): a **CNAME** record
     pointing to `cname.vercel-dns.com`
   - (Vercel shows the current values on the Domains page — use those over
     these, in case they've changed.)
4. Add those records at whichever registrar/DNS host manages your domain
   (Namecheap, GoDaddy, Cloudflare, Google Domains, etc.).
5. DNS usually propagates within minutes to a few hours. Vercel
   auto-provisions an SSL certificate once it verifies the records — no
   extra setup needed.
6. If you want `eatwellspendless.com` to redirect to `www` (or vice versa),
   set your preferred one as the primary domain on that same Domains page.

### Notes

- `CHECKOUT_URL` in `app.py` is the single source of truth for all three
  "Get instant access" buttons — change it there if the checkout link
  ever changes, then redeploy.
- Static assets (`static/css`, `static/js`, `static/images`) are bundled
  into the serverless function via `includeFiles` in `vercel.json` — no
  separate static hosting step needed.

## The Grocery Budget Check-In quiz

Lives at `/quiz` (linked from the nav, the footer and a teaser on the home page).
Eight one-question screens, an optional review step, a personalised result, then
the e-book offer. **Everything runs in the visitor's browser: answers are never
sent to the server or stored.**

Files: `static/js/quiz-data.js` (questions, scoring, all result wording — edit
copy here), `static/js/quiz.js` (screens and interaction), `static/css/quiz.css`,
`templates/quiz.html`, `templates/components/{quiz_intro,avatar,icons,quiz_teaser}.html`.

### The required entry popup (home page)
When someone first opens the home page, the quiz appears in a popup they must
complete before they can use the site. When they finish, they see a message
written for their main challenge (wasting food, planning, spending or shopping)
that frames the book as the answer to it, then a button that takes them into the
site: the page gets a "Picked for you" strip, a retargeted hero line, and the
most relevant chapters are marked. The full results page (score, three steps,
plan) is still available at `/quiz`.

- **It's a real modal dialog:** the page behind is inert, keyboard focus is trapped
  inside, Esc and clicking outside do nothing, and there is no skip button.
- **Returning visitors aren't gated again.** The browser remembers only "completed",
  the level and the theme for 30 days, on the visitor's own device. Never answers.
  "Retake the quiz" in the strip clears it.
- **It never traps anyone.** Without JavaScript there is no popup. If the quiz
  scripts or the popup stylesheet fail to load, the visitor is let in after a moment.
- **Turn it off** with the environment variable `QUIZ_GATE=false` (then redeploy).
  The home page returns to normal and shows the "Take the quiz" teaser instead.
- Copy for the four messages lives in `GATE` inside `static/js/quiz-data.js`;
  popup behaviour in `static/js/gate.js`; styling in `static/css/gate.css`.

*Worth knowing:* a required popup usually means fewer visitors reach the page,
and Google can mark full-screen popups on mobile search results as "intrusive
interstitials", which can affect search ranking. If traffic or sales dip, the
switch above makes it easy to compare with and without it.

### How the score works
- Answers to questions 1–6 add "room to improve" points in four areas: spending
  control, shopping habits, meal planning, food waste. Helpful habits add 0.
- Each area becomes a percentage of its own maximum; the four areas count equally;
  the score is their average, rounded (0–100). **Higher = more room to improve.**
- Questions 7–8 (goal, what it would give you) are *not* scored; they only
  personalise the wording and which parts of the book are listed first.
- Levels: 0–24 → 1, 25–49 → 2, 50–74 → 3, 75–100 → 4.
- Results are labelled an informal self-assessment, not financial advice.

### Optional settings (environment variables)
Set these locally in your shell, or on Vercel under *Project → Settings →
Environment Variables* (then redeploy). **None are required.**

| Variable | What it does | If unset |
|---|---|---|
| `PRODUCT_PRICE` e.g. `$9.99` | Shows the real price beside the checkout button | The page says the price is shown at checkout (nothing is invented) |
| `EMAIL_WEBHOOK_URL` | Turns on the optional "email me my results" box. The server forwards each consented sign-up as JSON to this URL (Zapier / Make / n8n catch-hook, or your email provider's endpoint) | The email box is not shown at all |
| `PLAUSIBLE_DOMAIN` e.g. `yourdomain.com` | Loads cookieless Plausible analytics | No analytics script, nothing tracked |
| `QUIZ_GATE` (`true`/`false`) | Whether the quiz is a required popup on the home page | `true` (popup on) |

**Email:** nothing is stored by this site. The webhook receives
`{email, consent, consent_text, source, level, score, challenges}`; *you* must
connect it to something that actually sends the email and honours unsubscribe
requests. The visitor must tick an (unticked by default) consent box, and results
are shown without ever asking for an email.

**Analytics events** (never include answers or emails): `Quiz Started`,
`Quiz Completed` (level only), `Plan Revealed`, `Checkout Click` (which button),
`Email Signup`, `Gate Shown`, `Gate Continue` (theme only).

### Tests
```
node tests/test_quiz_logic.js          # every one of the 102,400 answer combinations
python tests/audit_server_and_engine.py # email endpoint, score boundaries, copy scan
pip install playwright && playwright install chromium
python tests/e2e_audit.py              # real-browser run through the whole quiz
python tests/audit_analytics.py        # analytics events + checkout behaviour
python tests/e2e_gate.py               # the required popup: modal behaviour, themed messages, fail-open
python tests/test_app.py               # backend
python tests/e2e_quiz.py               # longer, independent run through the quiz page (takes a few minutes)
```

### Things to know
- Phone/browser "Back" leaves the quiz page (or, in the popup, the site); the on-screen Back button moves
  between questions. Progress is deliberately not saved (privacy).
- Add a privacy policy / contact page before switching on email collection; the
  consent text promises unsubscribe-on-request, which your email tool must support.

## Content source

All copy, chapter titles, recipes, prices, and savings figures are pulled directly
from the supplied e-book, 30-day challenge, and savings-calculator material. Nothing
about the business was invented; where the source material didn't specify something
(e.g. file format on delivery), the copy stays general rather than making a claim.
