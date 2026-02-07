import os
from flask import (Flask, render_template, request, redirect, url_for, flash, make_response, jsonify)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import bcrypt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'data/polls.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(200), nullable=False)
    options = db.relationship('Option', backref='poll', cascade="all, delete-orphan")

    def total_votes(self):
        return db.session.query(func.count(Vote.id)).join(Option).filter(Option.poll_id == self.id).scalar()

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(100), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    votes = db.relationship('Vote', backref='option', cascade="all, delete-orphan")

    def vote_count(self):
        return len(self.votes)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey('option.id'), nullable=False)

# --- Database Initialization ---
def init_db():
    if not os.path.exists('data/polls.db'):
        db.create_all()
        # Seed data
        seed_polls = [
            {'question': 'What is your favorite programming language?', 'options': ['Python', 'JavaScript', 'Rust', 'Go']},
            {'question': 'Which frontend framework do you prefer?', 'options': ['React', 'Vue', 'Svelte', 'Angular']},
            {'question': 'What is the best way to spend a weekend?', 'options': ['Coding a side project', 'Hiking in the mountains', 'Reading a book', 'Watching movies']}
        ]

        for poll_data in seed_polls:
            new_poll = Poll(question=poll_data['question'])
            db.session.add(new_poll)
            for option_text in poll_data['options']:
                new_option = Option(text=option_text, poll=new_poll)
                db.session.add(new_option)
        db.session.commit()

        # Add some votes
        import random
        all_options = Option.query.all()
        for _ in range(50):
            option = random.choice(all_options)
            vote = Vote(option_id=option.id)
            db.session.add(vote)
        db.session.commit()

@app.before_request
def before_first_request():
    if not os.path.exists('data'):
        os.makedirs('data')
    init_db()


# --- Admin ---
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = bcrypt.hashpw('admin'.encode('utf-8'), bcrypt.gensalt())

# --- Routes ---
@app.route('/')
def home():
    polls = Poll.query.all()
    return render_template('home.html', polls=polls)

@app.route('/poll/<int:poll_id>')
def poll_results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    total_votes = poll.total_votes()
    return render_template('results.html', poll=poll, total_votes=total_votes)

@app.route('/poll/<int:poll_id>/vote', methods=['GET', 'POST'])
def vote(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    if request.method == 'POST':
        if f'voted_{poll_id}' in request.cookies:
            flash("You have already voted in this poll.", "warning")
            return redirect(url_for('poll_results', poll_id=poll_id))

        option_id = request.form.get('option')
        if option_id:
            vote = Vote(option_id=option_id)
            db.session.add(vote)
            db.session.commit()
            flash("Your vote has been counted!", "success")
            response = make_response(redirect(url_for('poll_results', poll_id=poll_id)))
            response.set_cookie(f'voted_{poll_id}', 'true', max_age=60*60*24*365)
            return response
        else:
            flash("Please select an option.", "danger")

    return render_template('vote.html', poll=poll)

@app.route('/create', methods=['GET', 'POST'])
def create_poll():
    if 'admin_logged_in' not in request.cookies:
        return redirect(url_for('login'))

    if request.method == 'POST':
        question = request.form.get('question')
        options = request.form.getlist('options')
        options = [opt for opt in options if opt]

        if not question or len(options) < 2:
            flash("Please provide a question and at least two options.", "danger")
        else:
            poll = Poll(question=question)
            for opt_text in options:
                option = Option(text=opt_text, poll=poll)
                db.session.add(option)
            db.session.add(poll)
            db.session.commit()
            flash("Poll created successfully!", "success")
            return redirect(url_for('home'))

    return render_template('create_poll.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and bcrypt.checkpw(password.encode('utf-8'), ADMIN_PASSWORD_HASH):
            response = make_response(redirect(url_for('create_poll')))
            response.set_cookie('admin_logged_in', 'true')
            return response
        else:
            flash("Invalid credentials.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('home')))
    response.delete_cookie('admin_logged_in')
    return response

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
