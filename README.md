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

## Content source

All copy, chapter titles, recipes, prices, and savings figures are pulled directly
from the supplied e-book, 30-day challenge, and savings-calculator material. Nothing
about the business was invented; where the source material didn't specify something
(e.g. file format on delivery), the copy stays general rather than making a claim.
