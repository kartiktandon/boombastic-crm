# Pulse CRM (FastAPI + MongoDB)

Reference-inspired growth CRM with six connected modules: Dashboard, Leads,
Meetings, Proposals, Agreements, and Projects.

## Structure

```
crm/
  backend/
    main.py            FastAPI app, mounts all routers
    db.py               Mongo connection + collection handles
    models.py           Pydantic schemas for every entity
    utils.py            ObjectId <-> string helpers
    routes/
      leads.py
      meetings.py
      proposals.py
      agreements.py
      projects.py
      dashboard.py      Aggregation pipelines for stats
    requirements.txt
  frontend/
    index.html
    style.css
    app.js              Responsive vanilla JS CRM SPA
```

## Run it

**1. MongoDB** — install locally or use a free Atlas cluster.
```bash
# local (Ubuntu example)
sudo apt install -y mongodb
sudo systemctl start mongod
```
Or set `MONGO_URI` in your environment to an Atlas connection string.

**2. Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
Visit `http://localhost:8000/docs` for interactive API docs (Swagger).

**3. Frontend**
Just open `frontend/index.html` in a browser, or serve it:
```bash
cd frontend
python3 -m http.server 5500
```
Then visit `http://localhost:5500`, create an account, and sign in. The
frontend calls `http://localhost:8000` by default. To use another API origin,
set `localStorage.crm_api` in the browser before loading the app.

Set these backend variables for deployment:

```bash
export MONGO_URI='mongodb+srv://...'
export JWT_SECRET='use-a-long-random-secret'
export CORS_ORIGINS='https://your-frontend.example'
```

## Meta Lead Ads integration

The API exposes `GET/POST /webhooks/meta`. Meta verifies the endpoint with the
GET request, then sends signed lead notifications to the POST request. The API
uses each notification's `leadgen_id` to retrieve the submitted fields through
Graph API v26.0 and inserts the lead into MongoDB with `source: "meta"`.
Duplicate webhook deliveries are ignored using the unique `meta_lead_id`.

Configure these variables in your deployment platform's secret manager:

- `META_VERIFY_TOKEN` — a private value you choose and enter in Meta's webhook
  configuration.
- `META_APP_SECRET` — the App Secret from the Meta App Dashboard.
- `META_PAGE_ACCESS_TOKEN` — a long-lived Page access token with lead access.
- `META_GRAPH_VERSION` — optional; defaults to `v26.0`.

Do not put these values in source control, frontend code, URLs, or logs.

### Meta setup

1. Deploy the backend to a public HTTPS URL with a valid certificate. Meta does
   not accept localhost or self-signed certificates for webhooks.
2. In [Meta for Developers](https://developers.facebook.com/), create a
   Business app and connect the Facebook Page that owns the Lead Ads form.
3. Add the Webhooks product, choose the **Page** object, and use
   `https://YOUR-API/webhooks/meta` as the callback URL. Enter the same private
   verify token stored as `META_VERIFY_TOKEN`.
4. Subscribe the Page webhook to the `leadgen` field.
5. Grant the app `leads_retrieval` and `pages_manage_metadata`. During
   development, app admins/testers can test in development mode; production
   access may require Meta App Review and Business Verification.
6. Generate a long-lived Page access token, store it only as
   `META_PAGE_ACCESS_TOKEN`, and subscribe the app to the Page's
   `subscribed_apps` edge with `subscribed_fields=leadgen`.
7. Use Meta's Lead Ads Testing Tool to create a test lead. It should appear in
   the CRM under the **Meta** platform filter.

Meta forms must collect at least an email address or phone number. Standard
fields are mapped into the CRM; other form answers are retained in the
`meta_fields` object on the MongoDB lead document.

## Data model notes (why it's not a 1:1 SQL port)

- `notes` are embedded inside `leads` (small, bounded, always read with the lead)
  instead of a separate `lead_notes` table + JOIN.
- `line_items` are embedded inside `proposals` for the same reason.
- `meetings`, `proposals`, `agreements`, `projects` each store a `lead_id`
  reference rather than embedding, since they're queried independently and
  can grow unbounded per lead.
- Dashboard stats use MongoDB aggregation pipelines (`$group`, `$match`,
  `$sum`) instead of SQL `GROUP BY` — see `routes/dashboard.py`.

## What's stubbed / left for you

- File upload and e-signature integrations (agreements currently retain a URL
  and lifecycle state).
- PDF generation and delivery integrations for proposal/agreement documents.
- Team invitations, granular role policies, and audit-log UI.
- Automated database migrations and a production test suite.

## Tested

The API schema and frontend JavaScript have been syntax-checked. Use a real
MongoDB instance to run the authenticated end-to-end workflow.
