from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file
#===#
app = Flask(__name__)
app.config["DEBUG"] = True

app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+mysqlconnector://{os.environ['DATABASE_USERNAME']}" \
                                          f":{os.environ['DATABASE_PASSWORD']}" \
                                          f"@{os.environ['DATABASE_HOSTNAME']}" \
                                          f"/{os.environ['DATABASE_NAME']}"
app.config["SQLALCHEMY_POOL_RECYCLE"] = 299
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Comment(db.Model):

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(4096))

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        try:
            comments = Comment.query.all()
            return render_template("contact.html", comments=comments)
        except Exception as e:
            print(f"Error fetching comments: {e}")
            return "An error occurred while fetching comments."

    comment = Comment(content=request.form["contents"])
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('contact'))

# Home route
@app.route('/')
def home():
    return render_template('home.html')

# About route
@app.route('/about')
def about():
    return render_template('about.html')

# Run the application
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

