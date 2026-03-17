# Deploying the App and Adding Secure Payments

This guide walks through (1) deploying the app to a domain and (2) adding secure payments so users can pay to use it.

---

## Pricing research (suggested price)

Quick research on comparable products and consumer app pricing:

- **March Madness–specific tools:** Paid bracket simulators and picks (e.g. FTN Fantasy’s bracket simulator, Basketball Index’s March Madness package, PoolGenius/TeamRankings) sit in the **$35+** range for full data suites or heavy simulation tools. Your app is closer to a focused “AI fill + export” utility than those full platforms.
- **Indie / utility apps:** One-time prices of **$4.99–$9.99** are common and well received; **$4.99** is often cited as a good balance of low friction and perceived value, especially for one-time purchase (no subscription).
- **What you offer:** Model-based bracket fill, optional sentiment/prompt bias, export (JSON/PDF), PWA. It’s a single-season, fun utility rather than an ongoing data subscription.

**Suggested price:** **$4.99 one-time** per tournament (or **$6.99** if you want a bit more margin). Alternatives: **$2.99** to maximize volume, or **$9.99** if you position it as a premium “AI bracket” tool. You can A/B test later; starting at **$4.99** is a reasonable default.

---

## Part 1: Secure payments (Stripe)

Stripe is PCI-compliant and handles card data; you never touch raw card numbers. Use **Stripe Checkout** or **Stripe Payment Links** for the simplest integration.

### 1.1 Create a Stripe account and get keys

1. Sign up at [stripe.com](https://stripe.com).
2. In the [Dashboard](https://dashboard.stripe.com) go to **Developers → API keys**.
3. Copy your **Publishable key** (starts with `pk_`) and **Secret key** (starts with `sk_`). Use **Test** keys while building; switch to **Live** when you go live.
4. Never commit secret keys to git. Use environment variables (e.g. `STRIPE_SECRET_KEY`).

### 1.2 Create a product and price

1. In Stripe: **Product catalog → Add product**.
2. Name it (e.g. “March Madness Bracket – Full access”).
3. Add a **Price**: one-time or recurring (recommended: **$4.99 one-time** per season; see pricing section above).
4. Copy the **Price ID** (e.g. `price_xxxx`). You’ll use this in your app.

### 1.3 Integrate payment in your app

**Option A – Payment Link (no backend payment code)**  
- In Stripe: **Payment links → Create link** → choose your product/price.  
- Share the link (e.g. “Subscribe” or “Unlock” button).  
- After payment, Stripe can redirect to a “thank you” URL.  
- To **gate the app**, you need at least one of: (1) Stripe Customer Portal + email, (2) webhook + your DB, or (3) Stripe Checkout Session + webhook (Option B).

**Option B – Checkout Session (recommended for “pay to use”)**  
- **Backend**: Create a Stripe Checkout Session with the Price ID; return the session `url` to the frontend.  
- **Frontend**: Redirect the user to that URL. After payment, Stripe redirects back to your success URL (e.g. `/bracket` with a query like `?session_id=...`).  
- **Webhook**: On your backend, listen for `checkout.session.completed`. When you receive it, record the payment (e.g. store `customer_id` or `subscription_id` and link to the user or session).  
- **Gating**: Before serving the bracket/fill API, check (in your backend or in a small “auth” API) that the current user/session has a completed payment (e.g. by `session_id` or by stored customer/subscription). If not, return 402 or redirect to pay.

**Minimal backend (FastAPI) example**

```python
# backend/main.py or a separate router
import os
import stripe
from fastapi import APIRouter, HTTPException

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
router = APIRouter()

@router.post("/create-checkout-session")
def create_checkout_session(price_id: str, success_url: str, cancel_url: str):
    session = stripe.checkout.Session.create(
        mode="payment",  # or "subscription"
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    return {"url": session.url}

# Webhook: Stripe sends events here. Verify signature and store payment.
@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, body: bytes, stripe_signature: str = Header(None)):
    payload = body
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, os.environ["STRIPE_WEBHOOK_SECRET"]
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # Store session["customer_email"] or session["id"] in your DB; mark user as paid.
    return {"status": "ok"}
```

- **Frontend**: Call `POST /create-checkout-session` with your price ID and redirect the user to `url`. On the success page, you can pass `session_id` to your backend to verify and then allow access.

### 1.4 Webhook secret

1. In Stripe: **Developers → Webhooks → Add endpoint**.  
2. URL: `https://your-backend-domain.com/stripe-webhook` (use your real backend URL after deploy).  
3. Event: `checkout.session.completed`.  
4. Copy the **Signing secret** (e.g. `whsec_...`) into `STRIPE_WEBHOOK_SECRET` on the backend.

### 1.5 Security checklist

- Use **HTTPS** everywhere (automatic on Vercel/Railway/Render).  
- Store **STRIPE_SECRET_KEY** and **STRIPE_WEBHOOK_SECRET** only in server env vars, never in the frontend.  
- Verify webhook signatures with `stripe.Webhook.construct_event`.  
- In production, use **Live** API keys and live webhook endpoints.

---

## Part 2: Deploy to a domain

High-level: deploy **frontend** and **backend** separately, then point a **domain** (and optional subdomain) to each.

### 2.1 Deploy frontend (Next.js) – Vercel

1. Push your code to **GitHub** (or GitLab/Bitbucket).  
2. Go to [vercel.com](https://vercel.com), sign in with GitHub.  
3. **Add New Project** → Import your repo.  
4. **Root directory**: set to `frontend` (if the repo root is the monorepo).  
5. **Environment variables** (Vercel → Project → Settings → Environment Variables):  
   - `NEXT_PUBLIC_API_URL` = `https://your-backend-domain.com` (no trailing slash; your backend URL from step 2.2).  
6. Deploy. Vercel gives you a URL like `your-app.vercel.app`.  
7. (Optional) Add a **custom domain** in Vercel (Project → Settings → Domains). Use the same domain you’ll configure in 2.3 (e.g. `app.yourdomain.com` or `yourdomain.com`).

### 2.2 Deploy backend (FastAPI) – Railway or Render

**Option A – Railway**

1. Go to [railway.app](https://railway.app), sign in with GitHub.  
2. **New Project** → **Deploy from GitHub repo** → select your repo.  
3. Set **Root Directory** to `backend` (if applicable).  
4. **Variables**: add env vars (e.g. `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`; any others your app needs).  
5. **Settings**: set start command, e.g. `uvicorn main:app --host 0.0.0.0 --port $PORT`. Railway sets `PORT`.  
6. Deploy. Note the generated URL (e.g. `your-app.up.railway.app`).  
7. (Optional) Add a **custom domain** in Railway (e.g. `api.yourdomain.com`).

**Option B – Render**

1. Go to [render.com](https://render.com), sign in with GitHub.  
2. **New** → **Web Service** → connect repo, root directory `backend`.  
3. **Build**: `pip install -r requirements.txt` (or add a simple `Dockerfile` if you prefer).  
4. **Start**: `uvicorn main:app --host 0.0.0.0 --port $PORT`.  
5. Add **Environment** variables in the dashboard.  
6. Deploy. Use the default URL or add a custom domain (e.g. `api.yourdomain.com`).

**CORS**

- In `backend/main.py`, set `allow_origins` to your frontend origin(s), e.g. `https://your-app.vercel.app` and `https://yourdomain.com`.  
- Never use `"*"` in production if the frontend sends credentials or sensitive headers.

### 2.3 Point a domain to your app

1. **Buy a domain** (e.g. Namecheap, Google Domains, Cloudflare Registrar, Porkbun).  
2. **Frontend (Vercel)**  
   - In Vercel: Project → Settings → Domains → add `yourdomain.com` or `app.yourdomain.com`.  
   - Vercel shows the required DNS records (usually **CNAME** for `www` or **A** for root).  
3. **Backend (Railway/Render)**  
   - In Railway/Render: add custom domain (e.g. `api.yourdomain.com`).  
   - They will show a **CNAME** (or A) target.  
4. **At your domain registrar**  
   - Add the records Vercel and Railway/Render show (e.g. CNAME `api` → Railway host, CNAME `www` or A for root → Vercel).  
   - Propagation can take a few minutes up to 48 hours.  
5. **SSL**  
   - Vercel and Railway/Render provide HTTPS automatically for your custom domain once DNS is correct.

### 2.4 Environment variables summary

| Where        | Variable                   | Example / note                          |
|-------------|----------------------------|-----------------------------------------|
| Frontend    | `NEXT_PUBLIC_API_URL`      | `https://api.yourdomain.com`            |
| Backend     | `STRIPE_SECRET_KEY`        | `sk_live_...` (live) or `sk_test_...`   |
| Backend     | `STRIPE_WEBHOOK_SECRET`    | `whsec_...` from Stripe webhook         |
| Backend     | Any other (e.g. Ollama)    | As needed                               |

---

## Part 3: Gating the app after payment

- **Without user accounts**: Use Stripe Checkout; on success redirect with `session_id`. Your backend can expose an endpoint like `GET /api/verify-access?session_id=...` that checks (via Stripe API) whether that session is paid and returns 200/402. Frontend calls this before showing the bracket; if 402, show “Pay to unlock” and redirect to Checkout.  
- **With user accounts**: Add auth (e.g. NextAuth, Clerk, or Supabase Auth). After login, link the user to a Stripe `customer_id` or store “paid” in your DB when the webhook fires. Then gate API routes and UI on “user is logged in and has paid.”

---

## Quick reference

1. **Payments**: Stripe account → Product/Price → Checkout Session + webhook → verify payment before allowing use.  
2. **Deploy**: Frontend on Vercel, backend on Railway or Render; set env vars and CORS.  
3. **Domain**: Buy domain → add CNAME/A records for frontend and backend → attach domains in Vercel and Railway/Render.  
4. **Security**: HTTPS only, secret keys only on server, verify Stripe webhooks.

For more detail:  
- [Stripe Checkout](https://stripe.com/docs/checkout)  
- [Stripe Webhooks](https://stripe.com/docs/webhooks)  
- [Vercel custom domains](https://vercel.com/docs/concepts/projects/domains)  
- [Railway custom domains](https://docs.railway.app/reference/custom-domains)  
- [Render custom domains](https://render.com/docs/custom-domains)
