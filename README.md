# QueueLess

Smart virtual queue management — join a queue remotely, track your position live,
and walk in only when your turn is close. Includes a user-facing queue tracker
and an admin control console.

## Stack
- **Backend:** Python Flask + SQLite (`app.py`)
- **Frontend:** Server-rendered HTML (Jinja2) + vanilla JS polling, no build step
- **Fonts:** Fraunces (display), Inter (body/UI), JetBrains Mono (tokens/data)

## Run it

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. The database (`queueless.db`) is created and
seeded automatically on first run with four sample services: Student Office,
Campus Clinic, IT Help Desk, Customer Service.

## Using it

- **As a user:** open a service from the home page → *Join queue* → your
  digital ticket appears and updates live (polls every 3s) as the queue moves
  through Waiting → Almost up → Next → Your turn. Your ticket is remembered
  in the browser (localStorage), so you can close the tab and come back.
- **As an admin:** go to `/admin/<service-slug>` (e.g. `/admin/student-office`,
  linked from the home page) → *Call next* completes whoever is currently being
  served and pulls the next waiting token. *No-show, skip* cancels the current
  token without completing it.

## Project structure

```
app.py                  Flask app: routes, API, SQLite schema/seed
requirements.txt
templates/
  base.html              Shared shell, fonts, nav
  index.html             Landing page + service selection
  ticket.html            User-side live ticket tracker
  admin.html             Admin control console
static/
  css/style.css          Design tokens + all styling
  js/ticket.js            User polling + progress logic
  js/admin.js             Admin polling + call-next logic
```

## API reference

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/services` | List services with live counts |
| POST | `/api/queue/<slug>/join` | Create a new token, join the queue |
| GET | `/api/queue/<slug>/status/<token_id>` | Poll a specific token's status |
| GET | `/api/queue/<slug>/state` | Current serving token + waiting count |
| POST | `/api/admin/<slug>/call-next` | Complete current, serve next |
| POST | `/api/admin/<slug>/skip` | Cancel current token (no-show) |
| GET | `/api/admin/<slug>/queue` | Full waiting list + today's stats |

## Notes / next steps if you extend it

- Swap SQLite for Postgres (RDS) and wrap this in a Terraform + GitHub Actions
  pipeline if you want to fold it into your AWS/DevOps portfolio work.
- Add admin auth (currently the console is unauthenticated — fine for a demo,
  not for production).
- Swap polling for Server-Sent Events or WebSockets for instant updates at scale.
