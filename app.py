import os
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from prometheus_flask_exporter import PrometheusMetrics
metrics = PrometheusMetrics(app)   # exposes /metrics


app = Flask(__name__)
app.config["DEBUG"] = True

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")

USE_DB = all([DB_USER, DB_PASS, DB_HOST, DB_NAME])

db = SQLAlchemy()  # Do NOT pass app here

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(4096), nullable=False)

if USE_DB:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
    db.init_app(app)
else:
    _inmem = []

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        text = (request.form.get("contents") or "").strip()
        if text:
            if USE_DB:
                db.session.add(Comment(content=text))
                db.session.commit()
            else:
                _inmem.append({"content": text})
        return redirect(url_for("contact"))

    comments = Comment.query.order_by(Comment.id.desc()).all() if USE_DB else list(reversed(_inmem))
    return render_template("contact.html", comments=comments)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/dbcheck")
def dbcheck():
    return ("OK:DB" if USE_DB else "OK:NO-DB"), 200

if __name__ == "__main__":
    if USE_DB:
        with app.app_context():
            db.create_all()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)

