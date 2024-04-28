from flask import render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user, logout_user, login_user
from sqlalchemy_searchable import search
from hub.models import User, Game
from werkzeug import Response
from typing import Union
from app import app, db
import hub.discord as discord


@app.route('/connexion')
def login() -> Union[str, Response]:
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    return render_template(
        'login.html',
        login_discord_url=discord.generate_authorize_url()
    )


@app.route('/connexion/callback')
def login_callback() -> Union[str, Response]:
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    error = request.args.get('error')

    if error:
        error_description = request.args.get('error_description', 'aucune')

        flash(f'Erreur lors de la connexion avec Discord (code : {error} ; description : {error_description}).', 'error')

        return redirect(url_for('login'))

    state = request.args.get('state')
    code = request.args.get('code')

    if state != session.pop('oauth2_state', None) or not code:
        flash('Etat invalide ou code OAuth introuvable.', 'error')

        return redirect(url_for('login'))

    response = discord.get_oauth_token(code)

    if response.status_code != 200:
        flash('Erreur lors de la récupération du token auprès de Discord.', 'error')

        return redirect(url_for('login'))

    token = response.json()

    response = discord.get_membership_info(token)

    if response.status_code != 200:
        flash('Tu n\'est pas présent sur notre serveur Discord.', 'error')

        return redirect(url_for('login'))

    membership_info = response.json()
    user_roles = membership_info.get('roles', [])

    if not str(app.config['DISCORD_MEMBER_ROLE_ID']) in user_roles:
        flash('Seuls les membres de la team peuvent accéder à notre intranet.', 'error')

        return redirect(url_for('login'))

    user_info = membership_info.get('user', {})
    discord_id = user_info.get('id')

    user = db.session.get(User, discord_id)
    new_user = False

    if not user:
        user = User()
        user.id = discord_id

        new_user = True

    user.display_name = membership_info.get('nick', user_info.get('global_name', user_info.get('username')))

    member_avatar_hash = membership_info.get('avatar')
    user_avatar_hash = user_info.get('avatar')

    if member_avatar_hash:
        guild_id = app.config['DISCORD_GUILD_ID']

        user.avatar_url = f'https://cdn.discordapp.com/guilds/{guild_id}/users/{discord_id}/avatars/{member_avatar_hash}.png'
    elif user_avatar_hash:
        user.avatar_url = f'https://cdn.discordapp.com/avatars/{discord_id}/{user_avatar_hash}.png'

    user.is_lan_participant = str(app.config['DISCORD_LAN_PARTICIPANT_ROLE_ID']) in user_roles
    user.is_admin = str(app.config['DISCORD_ADMIN_ROLE_ID']) in user_roles

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


@app.route('/lan/jeux')
@login_required
def lan_games() -> Union[str, Response]:
    if not current_user.is_lan_participant and not current_user.is_admin:
        flash('Désolé, tu ne fait pas partie des participants à la LAN.', 'error')

        return redirect(url_for('home'))

    # print(discord.send_message(
    #     f'**Lan.Epoc** a proposé un nouveau jeu :',
    #     [
    #         {
    #             'type': 'rich',
    #             'title': 'RUNNING WITH RIFLES',
    #             'color': 0xf56b3d,
    #             'url': url_for('games', _external=True),
    #             'image': {
    #                 'url': 'https://cdn.cloudflare.steamstatic.com/steam/apps/270150/capsule_231x87.jpg',
    #             }
    #         }
    #     ]
    # ).text)

    return render_template('lan/games.html')


@app.route('/lan/jeux/recherche', methods=['POST'])
@login_required
def lan_games_search() -> str:
    games = [] # db.session.execute(search(db.select(Game), 'test')).scalars()

    return render_template('lan/partials/games_search_results.html', games=games)
