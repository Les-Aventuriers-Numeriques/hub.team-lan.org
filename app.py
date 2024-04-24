from flask import Flask, render_template, request, session
from werkzeug.exceptions import HTTPException
from flask_assets import Environment, Bundle
from sqlalchemy.orm import DeclarativeBase
from datetime import timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from typing import Tuple
from environs import Env

# -----------------------------------------------------------
# App bootstrap

env = Env()
env.read_env()

app = Flask(__name__)

app.config.update(
    # Default config values that may be overwritten by environment values
    SECRET_KEY=env.str('SECRET_KEY'),
    SERVER_NAME=env.str('SERVER_NAME', default='localhost:8080'),
    PREFERRED_URL_SCHEME=env.str('PREFERRED_URL_SCHEME', default='http'),

    SENTRY_DSN=env.str('SENTRY_DSN', default=None),
    SENTRY_TRACES_SAMPLE_RATE=env.float('SENTRY_TRACES_SAMPLE_RATE', default=None),

    ASSETS_CACHE=env.str('ASSETS_CACHE', default='instance/webassets-cache'),

    DEBUG_TB_INTERCEPT_REDIRECTS=env.bool('DEBUG_TB_INTERCEPT_REDIRECTS', False),

    MINIFY_HTML=env.bool('MINIFY_HTML', default=False),

    COMPRESS_REGISTER=env.bool('COMPRESS_REGISTER', default=False),
    COMPRESS_MIN_SIZE=env.int('COMPRESS_MIN_SIZE', 512),

    SQLALCHEMY_DATABASE_URI=env.str('SQLALCHEMY_DATABASE_URI', default='postgresql+psycopg2://postgre:postgre@localhost/postgre'),

    # Config values that cannot be overwritten
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),
    SESSION_PROTECTION='basic',
    BUNDLE_ERRORS=True,
)

# -----------------------------------------------------------
# Debugging-related behaviours

if app.config['DEBUG']:
    import logging

    logging.basicConfig(level=logging.DEBUG)
elif app.config['SENTRY_DSN']:
    try:
        from sentry_sdk.integrations.flask import FlaskIntegration
        import sentry_sdk

        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            integrations=[
                FlaskIntegration(),
            ],
            traces_sample_rate=app.config['SENTRY_TRACES_SAMPLE_RATE']
        )
    except ImportError:
        pass

# -----------------------------------------------------------
# Flask extensions initialization and configuration

# Flask-DebugToolbar
if app.config['DEBUG']:
    try:
        from flask_debugtoolbar import DebugToolbarExtension

        debug_toolbar = DebugToolbarExtension(app)
    except ImportError:
        pass

# Flask-Compress
try:
    from flask_compress import Compress

    compress = Compress(app)
except ImportError:
    pass

# Flask-HTMLmin
try:
    from flask_htmlmin import HTMLMIN

    htmlmin = HTMLMIN(app)
except ImportError:
    pass

# Flask-Assets
assets = Environment(app)
assets.append_path('assets')

assets.register('css_base', Bundle('css/base.css', filters='cssutils', output='css/base.min.css'))


# Flask-SQLAlchemy
class AppDeclarativeBase(DeclarativeBase):
    pass


db = SQLAlchemy(app, model_class=AppDeclarativeBase)

import hub.models

# Flask-Migrate
migrate = Migrate(app, db)

# Flask-Login
# login_manager = LoginManager(app)
# login_manager.login_message_category = 'success'


# @login_manager.user_loader
# def load_user(user_id: str):
#     from hub.models import User
#
#     return db.session.get(User, user_id)


# -----------------------------------------------------------
# Pre-request hooks

@app.before_request
def before_request():
    if request.endpoint and request.endpoint.startswith(('static', 'debugtoolbar', '_debug_toolbar')):
        return

    session.permanent = True


# -----------------------------------------------------------
# Error pages

@app.errorhandler(HTTPException)
def http_error_handler(e: HTTPException) -> Tuple[str, int]:
    return render_template(
        'error.html',
        title=e.name,
        text=e.description,
    ), e.code


# -----------------------------------------------------------
# After-bootstrap imports

import hub.routes
import hub.commands