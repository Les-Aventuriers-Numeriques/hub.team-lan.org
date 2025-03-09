from flask import Flask, render_template, request, session, g
from flask_discord_interactions import DiscordInteractions
from sqlalchemy_searchable import make_searchable
from werkzeug.exceptions import HTTPException
from flask_assets import Environment, Bundle
from sqlalchemy.orm import DeclarativeBase
from flask_babel import Babel, get_locale
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta, date
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_caching import Cache
from typing import Tuple, Dict
from environs import Env

# -----------------------------------------------------------
# Initialisation de l'application

env = Env()
env.read_env()

app = application = Flask(__name__)

app.config.update(
    # -----------------------------------------------------------
    # Configuration Flask

    SECRET_KEY=env.str('SECRET_KEY'),
    SERVER_NAME=env.str('SERVER_NAME', default='localhost:8080'),
    PREFERRED_URL_SCHEME=env.str('PREFERRED_URL_SCHEME', default='http'),

    # -----------------------------------------------------------
    # Configuration extensions

    # sentry-sdk[flask]
    SENTRY_DSN=env.str('SENTRY_DSN', default=None),
    SENTRY_TRACES_SAMPLE_RATE=env.float('SENTRY_TRACES_SAMPLE_RATE', default=None),

    # Flask-DebugToolbar
    DEBUG_TB_INTERCEPT_REDIRECTS=env.bool('DEBUG_TB_INTERCEPT_REDIRECTS', False),

    # Flask-Compress
    COMPRESS_REGISTER=env.bool('COMPRESS_REGISTER', default=False),

    # Flask-HTMLmin
    MINIFY_HTML=env.bool('MINIFY_HTML', default=False),

    # Flask-Caching
    CACHE_TYPE=env.str('CACHE_TYPE', default='FileSystemCache'),
    CACHE_DIR=env.str('CACHE_DIR', default='instance/cache'),
    CACHE_THRESHOLD=env.int('CACHE_THRESHOLD', default=500),

    # Flask-Assets
    ASSETS_CACHE=env.str('ASSETS_CACHE', default='instance/webassets-cache'),

    # Flask-Babel
    BABEL_DEFAULT_LOCALE=env.str('BABEL_DEFAULT_LOCALE', default='fr'),
    BABEL_DEFAULT_TIMEZONE=env.str('BABEL_DEFAULT_TIMEZONE', default='Europe/Paris'),

    # Flask-SQLAlchemy
    SQLALCHEMY_SCHEMA_NAME=env.str('SQLALCHEMY_SCHEMA_NAME', default='postgres'),
    SQLALCHEMY_DATABASE_URI=env.str('SQLALCHEMY_DATABASE_URI', default='postgresql+psycopg://postgres:postgres@localhost/postgres'),

    # -----------------------------------------------------------
    # Configuration app

    # API Steam
    STEAM_API_KEY=env.str('STEAM_API_KEY'),

    # API Discord
    DISCORD_CLIENT_ID=env.int('DISCORD_CLIENT_ID'),
    DISCORD_CLIENT_SECRET=env.str('DISCORD_CLIENT_SECRET'),
    DISCORD_PUBLIC_KEY=env.str('DISCORD_PUBLIC_KEY'),
    DISCORD_BOT_TOKEN=env.str('DISCORD_BOT_TOKEN', None),
    DISCORD_GUILD_ID=env.int('DISCORD_GUILD_ID'),
    DISCORD_MEMBER_ROLE_ID=env.int('DISCORD_MEMBER_ROLE_ID'),
    DISCORD_LAN_PARTICIPANT_ROLE_ID=env.int('DISCORD_LAN_PARTICIPANT_ROLE_ID'),
    DISCORD_ADMIN_ROLE_ID=env.int('DISCORD_ADMIN_ROLE_ID'),
    DISCORD_LAN_CHANNEL_ID=env.int('DISCORD_LAN_CHANNEL_ID', None),
    DISCORD_PUBG_CHANNEL_ID=env.int('DISCORD_PUBG_CHANNEL_ID', None),

    # API PUBG
    PUBG_API_JWT_TOKEN=env.str('PUBG_API_JWT_TOKEN', None),
    PUBG_PLAYER_NAMES_INTERNAL=env.list('PUBG_PLAYER_NAMES_INTERNAL', []),
    PUBG_PLAYER_NAMES_EXTERNAL=env.list('PUBG_PLAYER_NAMES_EXTERNAL', []),

    # -----------------------------------------------------------
    # Valeurs de configuration qui ne peuvent pas être surchargées

    PERMANENT_SESSION_LIFETIME=timedelta(days=365),
    BUNDLE_ERRORS=True,
    USE_SESSION_FOR_NEXT=True,

    TOP_LAN_GAME_PROPOSALS=12,

    DISCORD_INTERACTIONS_PATH='/discord-interactions',
)

# -----------------------------------------------------------
# Initialisation du SDK Sentry

if app.config['SENTRY_DSN']:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            traces_sample_rate=app.config['SENTRY_TRACES_SAMPLE_RATE'],
            send_default_pii=True
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

assets.register('css_base', Bundle('css/base.css', filters='rcssmin', output='css/base.min.css'))
assets.register('css_lan_games', Bundle('css/base.css', 'css/lan_games.css', filters='rcssmin', output='css/lan_games.min.css'))
assets.register('css_lan_games_vote', Bundle('css/base.css', 'css/lan_games.css', 'css/lan_games_vote.css', filters='rcssmin', output='css/lan_games_vote.min.css'))
assets.register('css_lan_games_proposal', Bundle('css/base.css', 'css/lan_games.css', 'css/lan_games_proposal.css', filters='rcssmin', output='css/lan_games_proposal.min.css'))

# Flask-Babel
babel = Babel(app)

# Flask-Discord-Interactions
discord_interactions = DiscordInteractions(app)
discord_interactions.set_route(app.config['DISCORD_INTERACTIONS_PATH'])

# Flask-Caching
cache = Cache(app)

# Flask-SQLAlchemy
class AppDeclarativeBase(DeclarativeBase):
    pass


db = SQLAlchemy(app, model_class=AppDeclarativeBase)

make_searchable(db.metadata, options={'regconfig': app.config['SQLALCHEMY_SCHEMA_NAME'] + '.english_nostop'})

# Flask-Migrate
migrate = Migrate(app, db)

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Merci de te connecter afin d\'accéder à cette page, on se revoit ensuite.'
login_manager.login_message_category = 'error'


@login_manager.user_loader
def load_user(user_id: str):
    from hub.models import User

    return db.session.get(User, user_id)


# -----------------------------------------------------------
# Ecouteurs pré-requête

@app.before_request
def before_request():
    from hub.models import Setting

    if request.endpoint and request.endpoint.startswith(('static', 'debugtoolbar', '_debug_toolbar')):
        return

    g.lan_games_status =  Setting.get('lan_games_status', 'disabled')

    if request.path == app.config['DISCORD_INTERACTIONS_PATH']:
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
# Gestionnaire de page d'erreur personalisée

@app.errorhandler(HTTPException)
def http_error_handler(e: HTTPException) -> Tuple[str, int]:
    return render_template(
        'error.html',
        name=e.name,
        description=e.description,
    ), e.code


# -----------------------------------------------------------
# Imports post-initialisation

import hub.models
import hub.routes
import hub.commands
