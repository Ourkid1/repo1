import os
from urllib.parse import quote_plus
from flask import Flask, redirect, render_template, request, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, func

# Optional: Prometheus metrics
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

DEBUG = os.getenv("DEBUG", "0") == "1"
app.config["DEBUG"] = DEBUG

# ---- DB config ----
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS") or os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DATABASE_URL = os.getenv("DATABASE_URL")

USE_DB = bool(DATABASE_URL) or all([DB_USER, DB_PASS, DB_HOST, DB_NAME])

db = SQLAlchemy()

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(4096), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="suggestion")   # NEW
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)  # NEW

if USE_DB:
    if not DATABASE_URL:
        DB_URI = (
            f"mysql+mysqlconnector://{DB_USER}:{quote_plus(DB_PASS)}@{DB_HOST}/{DB_NAME}"
            "?charset=utf8mb4"
        )
    else:
        DB_URI = DATABASE_URL

    app.config.update(
        SQLALCHEMY_DATABASE_URI=DB_URI,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True, "pool_recycle": 299},
    )
    db.init_app(app)

    with app.app_context():
        try:
            # ensure new cols exist even if table already created
            db.create_all()
            # optional: try to backfill columns if old schema
            try:
                db.session.execute(text("ALTER TABLE comments ADD COLUMN kind VARCHAR(20) NOT NULL DEFAULT 'suggestion'"))
            except Exception:
                pass
            try:
                db.session.execute(text("ALTER TABLE comments ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"))
            except Exception:
                pass
            db.session.commit()
        except Exception as e:
            app.logger.warning(f"DB init skipped: {e!r}")
else:
    _inmem = []

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        # honeypot
        if (request.form.get("website") or "").strip():
            return redirect(url_for("contact"))

        kind = (request.form.get("kind") or "suggestion").strip().lower()
        if kind not in ("suggestion", "message"):
            kind = "suggestion"
        text_in = (request.form.get("contents") or "").strip()

        if not text_in:
            return render_template("contact.html", error="Please add some text.")

        try:
            if USE_DB:
                db.session.add(Comment(content=text_in, kind=kind))
                db.session.commit()
            else:
                _inmem.append({"content": text_in, "kind": kind})
        except Exception:
            app.logger.exception("DB insert failed")

        return redirect(url_for("contact", sent="1"))

    return render_template("contact.html")

@app.get("/")
def home():
    return render_template("home.html")

@app.get("/picks")
def picks():
    return render_template("picks.html")

@app.get("/dbcheck")
def dbcheck():
    if not USE_DB:
        return ("OK:NO-DB", 200)
    try:
        db.session.execute(text("SELECT 1"))
        return ("OK:DB", 200)
    except Exception as e:
        app.logger.exception("DB check failed")
        return (f"DB ERROR: {e}", 500)

# ---------- Prometheus /metrics (derived from DB on each scrape) ----------
@app.get("/metrics")
def metrics():
    registry = CollectorRegistry()
    total = Gauge("myapp_contact_total", "Total stored contact items", ["kind"], registry=registry)
    last24h = Gauge("myapp_contact_last24h", "Items stored in the last 24h", ["kind"], registry=registry)

    if USE_DB:
        # totals by kind
        rows = db.session.execute(text("SELECT kind, COUNT(*) FROM comments GROUP BY kind")).fetchall()
        by_kind = {k: c for k, c in rows}
        for k in ("suggestion", "message"):
            total.labels(kind=k).set(float(by_kind.get(k, 0)))

        # last 24h by kind
        rows24 = db.session.execute(text("""
            SELECT kind, COUNT(*)
            FROM comments
            WHERE created_at >= NOW() - INTERVAL 1 DAY
            GROUP BY kind
        """)).fetchall()
        by_kind24 = {k: c for k, c in rows24}
        for k in ("suggestion", "message"):
            last24h.labels(kind=k).set(float(by_kind24.get(k, 0)))
    else:
        # in-memory fallback
        from collections import Counter
        cnt = Counter([x.get("kind", "suggestion") for x in _inmem])
        for k in ("suggestion", "message"):
            total.labels(kind=k).set(float(cnt.get(k, 0)))
            last24h.labels(kind=k).set(float(cnt.get(k, 0)))  # naive fallback

    data = generate_latest(registry)
    return app.response_class(data, mimetype=CONTENT_TYPE_LATEST)

@app.get("/healthz")
def healthz():
    return jsonify(ok=True), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=DEBUG)
