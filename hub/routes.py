from flask import render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user, logout_user, login_user
from urllib.parse import urlencode
from werkzeug import Response
from hub.models import User
from typing import Union
from app import app, db
import requests
import secrets

requests = requests.Session()


@app.route('/connexion')
def login() -> Union[str, Response]:
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    session['oauth2_state'] = secrets.token_urlsafe(16)

    discord_qs = urlencode({
        'client_id': app.config['DISCORD_CLIENT_ID'],
        'redirect_uri': url_for('login_callback', _external=True),
        'response_type': 'code',
        'scope': ' '.join(app.config['DISCORD_SCOPES']),
        'state': session.get('oauth2_state'),
    })

    return render_template(
        'login.html',
        login_discord_url=app.config['DISCORD_AUTHORIZE_URL'] + '?' + discord_qs
    )


@app.route('/connexion/callback')
def login_callback() -> Union[str, Response]:
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    error = request.args.get('error')

    if error:
        error_description = request.args.get('error_description', 'aucune')

        flash(f'Erreur lors de la connexion (code : {error} ; description : {error_description}).', 'error')

        return redirect(url_for('login'))

    state = request.args.get('state')
    code = request.args.get('code')

    if state != session.pop('oauth2_state', None) or not code:
        flash('Etat invalide ou code introuvable.', 'error')

        return redirect(url_for('login'))

    response = requests.post(app.config['DISCORD_TOKEN_URL'], data={
        'client_id': app.config['DISCORD_CLIENT_ID'],
        'client_secret': app.config['DISCORD_CLIENT_SECRET'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': url_for('login_callback', _external=True),
    }, headers={'Accept': 'application/json'})

    if response.status_code != 200:
        flash('Erreur lors de la récupération du token.', 'error')

        return redirect(url_for('login'))

    token = response.json()

    guild_id = app.config['DISCORD_GUILD_ID']

    response = requests.get(f'https://discord.com/api/users/@me/guilds/{guild_id}/member', headers={
        'Authorization': '{token_type} {access_token}'.format(**token),
        'Accept': 'application/json',
    })

    if response.status_code != 200:
        flash('Erreur lors de la récupération de tes informations.', 'error')

        return redirect(url_for('login'))

    membership_info = response.json()
    user_roles =  membership_info.get('roles', [])

    if app.config['DISCORD_ROLE_ID'] not in user_roles:
        flash('Tu n\'as pas accès à ce site.', 'error')

        return redirect(url_for('login'))

    user_info = membership_info.get('user', {})
    discord_id = user_info.get('id')

    user = db.session.get(User, discord_id)
    new_user = False

    if not user:
        user = User()
        user.discord_id = discord_id

        new_user = True

    user.display_name = membership_info.get('nick', user_info.get('global_name', user_info.get('username')))

    member_avatar_hash = membership_info.get('avatar')
    user_avatar_hash = user_info.get('avatar')

    if member_avatar_hash:
        user.avatar_url = f'https://cdn.discordapp.com/guilds/{guild_id}/users/{discord_id}/avatars/{member_avatar_hash}.png'
    elif user_avatar_hash:
        user.avatar_url = f'https://cdn.discordapp.com/avatars/{discord_id}/{user_avatar_hash}.png'

    db.session.add(user)
    db.session.commit()

    login_user(user, remember=True)

    flash('{} {} !'.format('Bienvenue' if new_user else 'Content de te revoir', user.display_name), 'success')

    return redirect(url_for('home'))


@app.route('/deconnexion')
@login_required
def logout() -> Response:
    flash(f'À plus {current_user.display_name} !', 'success')

    logout_user()

    return redirect(url_for('login'))


@app.route('/')
@login_required
def home() -> str:
    return render_template('home.html')


@app.route('/jeux')
@login_required
def games() -> str:
    return render_template('games.html')
