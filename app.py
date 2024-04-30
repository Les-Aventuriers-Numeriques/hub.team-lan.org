from flask import Flask, render_template, request, session
from sqlalchemy_searchable import make_searchable
from werkzeug.exceptions import HTTPException
from flask_assets import Environment, Bundle
from sqlalchemy.orm import DeclarativeBase
from flask_babel import Babel, get_locale
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta, date
from flask_login import LoginManager
from flask_migrate import Migrate
from typing import Tuple, Dict
from environs import Env

# -----------------------------------------------------------
# Initialisation de l'application

env = Env()
env.read_env()

app = Flask(__name__)

app.config.update(
    # Valeurs de configuration par défaut qui peuvent être surchargées par des variables d'environnement
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

    BABEL_DEFAULT_LOCALE=env.str('BABEL_DEFAULT_LOCALE', default='fr'),
    BABEL_DEFAULT_TIMEZONE=env.str('BABEL_DEFAULT_TIMEZONE', default='Europe/Paris'),

    SQLALCHEMY_DATABASE_URI=env.str('SQLALCHEMY_DATABASE_URI', default='postgresql+psycopg2://postgres:postgres@localhost/postgres'),

    DISCORD_CLIENT_ID=env.int('DISCORD_CLIENT_ID'),
    DISCORD_CLIENT_SECRET=env.str('DISCORD_CLIENT_SECRET'),
    DISCORD_BOT_TOKEN=env.str('DISCORD_BOT_TOKEN'),
    DISCORD_GUILD_ID=env.int('DISCORD_GUILD_ID'),
    DISCORD_MEMBER_ROLE_ID=env.int('DISCORD_MEMBER_ROLE_ID'),
    DISCORD_LAN_PARTICIPANT_ROLE_ID=env.int('DISCORD_LAN_PARTICIPANT_ROLE_ID'),
    DISCORD_ADMIN_ROLE_ID=env.int('DISCORD_ADMIN_ROLE_ID'),
    DISCORD_LAN_CHANNEL_ID=env.int('DISCORD_LAN_CHANNEL_ID'),

    # Valeurs de configuration qui ne peuvent pas être surchargées
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),
    BUNDLE_ERRORS=True,
    USE_SESSION_FOR_NEXT=True
)

# -----------------------------------------------------------
# Comportements relatifs au debug

if app.config['SENTRY_DSN']:
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
# Initialisation et configuration des extensions Flask

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
assets.register('css_lan_games', Bundle('css/base.css', 'css/lan_games.css', filters='cssutils', output='css/lan_games.min.css'))
assets.register('css_lan_games_proposal', Bundle('css/base.css', 'css/lan_games.css', 'css/lan_games_proposal.css', filters='cssutils', output='css/lan_games_proposal.min.css'))

# Flask-Babel
babel = Babel(app)

# Flask-SQLAlchemy
class AppDeclarativeBase(DeclarativeBase):
    pass


db = SQLAlchemy(app, model_class=AppDeclarativeBase)

make_searchable(db.metadata)

import hub.models

# Flask-Migrate
migrate = Migrate(app, db)

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Merci de te connecter afin d\'accéder à cette page, on se revoit ensuite.'
login_manager.login_message_category = 'error'


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(hub.models.User, user_id)


# -----------------------------------------------------------
# Ecouteurs pré-requête

@app.before_request
def before_request():
    if request.endpoint and request.endpoint.startswith(('static', 'debugtoolbar', '_debug_toolbar')):
        return

    session.permanent = True


# -----------------------------------------------------------
# Pré-processeurs de contexte

@app.context_processor
def context_processor() -> Dict:
    return {
        'current_locale': get_locale,
        'today': date.today(),
    }


# -----------------------------------------------------------
# Page d'erreur

@app.errorhandler(HTTPException)
def http_error_handler(e: HTTPException) -> Tuple[str, int]:
    return render_template(
        'error.html',
        title=e.name,
        text=e.description,
    ), e.code


# -----------------------------------------------------------
# Imports post-initialisation

import hub.routes
import hub.commands
