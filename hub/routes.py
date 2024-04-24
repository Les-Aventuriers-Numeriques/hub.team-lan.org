from flask import render_template, redirect, url_for
from werkzeug import Response
from app import app


@app.route('/')
def home() -> Response:
    return redirect(url_for('games'))


@app.route('/jeux')
def games() -> str:
    return render_template('games.html')
