"""
QueueLess — Smart Virtual Queue Management
Flask backend + SQLite persistence.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000
"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, abort

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "queueless.db"
AVG_SERVICE_SECONDS = 4 * 60  # used to estimate wait time per person ahead

app = Flask(__name__)


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            prefix TEXT NOT NULL,
            icon TEXT DEFAULT 'ticket',
            next_number INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER NOT NULL REFERENCES services(id),
            label TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',  -- waiting | serving | completed | cancelled
            created_at TEXT NOT NULL,
            served_at TEXT,
            completed_at TEXT
        );
        """
    )
    db.commit()

    seed = [
        ("student-office", "Student Office", "A", "graduation-cap"),
        ("clinic", "Campus Clinic", "C", "cross"),
        ("help-desk", "IT Help Desk", "H", "life-buoy"),
        ("customer-service", "Customer Service", "S", "headset"),
    ]
    for slug, name, prefix, icon in seed:
        exists = db.execute("SELECT 1 FROM services WHERE slug=?", (slug,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO services (slug, name, prefix, icon, next_number) VALUES (?,?,?,?,1)",
                (slug, name, prefix, icon),
            )
    db.commit()
    db.close()


# --------------------------------------------------------------------------
# Small data helpers
# --------------------------------------------------------------------------

def get_service_or_404(slug):
    db = get_db()
    svc = db.execute("SELECT * FROM services WHERE slug=?", (slug,)).fetchone()
    if not svc:
        abort(404, description="Unknown service")
    return svc


def queue_state(service_id):
    """Returns (serving_token_or_None, waiting_tokens_list) ordered by creation."""
    db = get_db()
    serving = db.execute(
        "SELECT * FROM tokens WHERE service_id=? AND status='serving' ORDER BY served_at DESC LIMIT 1",
        (service_id,),
    ).fetchone()
    waiting = db.execute(
        "SELECT * FROM tokens WHERE service_id=? AND status='waiting' ORDER BY created_at ASC",
        (service_id,),
    ).fetchall()
    return serving, waiting


def token_to_dict(row, position=None, people_ahead=None, est_wait_min=None):
    if row is None:
        return None
    d = dict(row)
    if position is not None:
        d["position"] = position
    if people_ahead is not None:
        d["people_ahead"] = people_ahead
    if est_wait_min is not None:
        d["estimated_wait_minutes"] = est_wait_min
    return d


def today_stats(service_id):
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    served_today = db.execute(
        "SELECT COUNT(*) c FROM tokens WHERE service_id=? AND status='completed' AND completed_at LIKE ?",
        (service_id, f"{today}%"),
    ).fetchone()["c"]

    avg_row = db.execute(
        """SELECT AVG( (julianday(completed_at) - julianday(served_at)) * 24 * 60 ) avg_min
           FROM tokens
           WHERE service_id=? AND status='completed' AND served_at IS NOT NULL
             AND completed_at LIKE ?""",
        (service_id, f"{today}%"),
    ).fetchone()["avg_min"]

    waiting_count = db.execute(
        "SELECT COUNT(*) c FROM tokens WHERE service_id=? AND status='waiting'", (service_id,)
    ).fetchone()["c"]

    return {
        "served_today": served_today,
        "avg_service_minutes": round(avg_row, 1) if avg_row else None,
        "waiting_count": waiting_count,
    }


# --------------------------------------------------------------------------
# Page routes
# --------------------------------------------------------------------------

@app.route("/")
def home():
    db = get_db()
    services = db.execute("SELECT * FROM services ORDER BY name ASC").fetchall()
    cards = []
    for s in services:
        serving, waiting = queue_state(s["id"])
        cards.append(
            {
                **dict(s),
                "waiting_count": len(waiting),
                "now_serving": serving["label"] if serving else "—",
            }
        )
    return render_template("index.html", services=cards)


@app.route("/queue/<slug>")
def queue_page(slug):
    svc = get_service_or_404(slug)
    return render_template("ticket.html", service=dict(svc))


@app.route("/admin/<slug>")
def admin_page(slug):
    svc = get_service_or_404(slug)
    return render_template("admin.html", service=dict(svc))


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------

@app.route("/api/services")
def api_services():
    db = get_db()
    services = db.execute("SELECT * FROM services ORDER BY name ASC").fetchall()
    out = []
    for s in services:
        serving, waiting = queue_state(s["id"])
        out.append(
            {
                **dict(s),
                "waiting_count": len(waiting),
                "now_serving": serving["label"] if serving else None,
            }
        )
    return jsonify(out)


@app.route("/api/queue/<slug>/join", methods=["POST"])
def api_join(slug):
    svc = get_service_or_404(slug)
    db = get_db()
    number = svc["next_number"]
    label = f'{svc["prefix"]}{number:03d}'
    now = datetime.now().isoformat(timespec="seconds")

    db.execute(
        "INSERT INTO tokens (service_id, label, status, created_at) VALUES (?,?,?,?)",
        (svc["id"], label, "waiting", now),
    )
    db.execute("UPDATE services SET next_number = next_number + 1 WHERE id=?", (svc["id"],))
    db.commit()

    token_id = db.execute("SELECT last_insert_rowid() id").fetchone()["id"]
    return jsonify({"token_id": token_id, "label": label})


@app.route("/api/queue/<slug>/status/<int:token_id>")
def api_status(slug, token_id):
    svc = get_service_or_404(slug)
    db = get_db()
    token = db.execute(
        "SELECT * FROM tokens WHERE id=? AND service_id=?", (token_id, svc["id"])
    ).fetchone()
    if not token:
        abort(404, description="Unknown token")

    serving, waiting = queue_state(svc["id"])

    if token["status"] == "completed":
        return jsonify(token_to_dict(token))

    if token["status"] == "serving":
        return jsonify(token_to_dict(token, position=0, people_ahead=0, est_wait_min=0))

    waiting_ids = [w["id"] for w in waiting]
    if token["id"] in waiting_ids:
        idx = waiting_ids.index(token["id"])
        people_ahead = idx + (1 if serving else 0)
        est_wait = round((people_ahead * AVG_SERVICE_SECONDS) / 60)
        return jsonify(
            token_to_dict(token, position=idx + 1, people_ahead=people_ahead, est_wait_min=est_wait)
        )

    return jsonify(token_to_dict(token))


@app.route("/api/queue/<slug>/state")
def api_state(slug):
    svc = get_service_or_404(slug)
    serving, waiting = queue_state(svc["id"])
    return jsonify(
        {
            "service": dict(svc),
            "now_serving": token_to_dict(serving),
            "waiting_count": len(waiting),
            "waiting": [token_to_dict(w) for w in waiting],
            "stats": today_stats(svc["id"]),
        }
    )


@app.route("/api/admin/<slug>/call-next", methods=["POST"])
def api_call_next(slug):
    svc = get_service_or_404(slug)
    db = get_db()
    now = datetime.now().isoformat(timespec="seconds")

    current = db.execute(
        "SELECT * FROM tokens WHERE service_id=? AND status='serving'", (svc["id"],)
    ).fetchone()
    if current:
        db.execute(
            "UPDATE tokens SET status='completed', completed_at=? WHERE id=?", (now, current["id"])
        )

    nxt = db.execute(
        "SELECT * FROM tokens WHERE service_id=? AND status='waiting' ORDER BY created_at ASC LIMIT 1",
        (svc["id"],),
    ).fetchone()
    if nxt:
        db.execute("UPDATE tokens SET status='serving', served_at=? WHERE id=?", (now, nxt["id"]))

    db.commit()
    serving, waiting = queue_state(svc["id"])
    return jsonify(
        {
            "now_serving": token_to_dict(serving),
            "waiting_count": len(waiting),
            "waiting": [token_to_dict(w) for w in waiting],
        }
    )


@app.route("/api/admin/<slug>/skip", methods=["POST"])
def api_skip(slug):
    """Cancel the current serving token without advancing (edge case: no-show)."""
    svc = get_service_or_404(slug)
    db = get_db()
    now = datetime.now().isoformat(timespec="seconds")
    current = db.execute(
        "SELECT * FROM tokens WHERE service_id=? AND status='serving'", (svc["id"],)
    ).fetchone()
    if current:
        db.execute("UPDATE tokens SET status='cancelled', completed_at=? WHERE id=?", (now, current["id"]))
        db.commit()
    serving, waiting = queue_state(svc["id"])
    return jsonify({"now_serving": token_to_dict(serving), "waiting_count": len(waiting)})


@app.route("/api/admin/<slug>/queue")
def api_admin_queue(slug):
    svc = get_service_or_404(slug)
    serving, waiting = queue_state(svc["id"])
    return jsonify(
        {
            "service": dict(svc),
            "now_serving": token_to_dict(serving),
            "waiting": [token_to_dict(w) for w in waiting],
            "stats": today_stats(svc["id"]),
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
