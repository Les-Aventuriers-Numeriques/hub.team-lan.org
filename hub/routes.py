from hub.models import User, Game, LanGameProposal, LanGameProposalVote, LanGameProposalVoteType
from flask import render_template, redirect, url_for, flash, session, request
from flask_login import login_required, current_user, logout_user, login_user
from hub.forms import LanGamesProposalSearchForm
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound
from sqlalchemy_searchable import search
from werkzeug import Response
from typing import Union
from app import app, db
import sqlalchemy.orm as sa_orm
import hub.discord as discord
import sqlalchemy as sa


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
    if not current_user.can_access_lan_section:
        flash('Désolé, tu ne fait pas partie des participants à la LAN.', 'error')

        return redirect(url_for('home'))

    proposals = db.session.execute(
        sa.select(LanGameProposal)
        .options(
            sa_orm.selectinload(LanGameProposal.game),
            sa_orm.selectinload(LanGameProposal.user),
            sa_orm.selectinload(LanGameProposal.votes)
        )
    ).scalars().all()

    return render_template('lan/games.html', proposals=proposals)


@app.route('/lan/jeux/annuler-vote/<int:game_id>')
@login_required
def lan_games_proposal_cancel_vote(game_id: int) -> Response:
    if not current_user.can_access_lan_section:
        flash('Désolé, tu ne fait pas partie des participants à la LAN.', 'error')

        return redirect(url_for('home'))

    result = db.session.execute(
        sa.delete(LanGameProposalVote)
        .where(
            LanGameProposalVote.game_proposal_game_id == game_id,
            LanGameProposalVote.user_id == current_user.id
        )
    )

    db.session.commit()

    if result.rowcount == 1:
        flash('Ton vote a été annulé.', 'success')
    else:
        flash('Aucun vote à annuler.', 'error')

    return redirect(url_for('lan_games'))


@app.route('/lan/jeux/voter/<int:game_id>/<any({}):vote_type>'.format(','.join(LanGameProposalVoteType.values())))
@login_required
def lan_games_proposal_vote(game_id: int, vote_type: str) -> Response:
    if not current_user.can_access_lan_section:
        flash('Désolé, tu ne fait pas partie des participants à la LAN.', 'error')

        return redirect(url_for('home'))

    try:
        vote = LanGameProposalVote()
        vote.game_proposal_game_id = game_id
        vote.user_id = current_user.id
        vote.type = LanGameProposalVoteType(vote_type)

        db.session.add(vote)
        db.session.commit()

        flash('A voté !', 'success')
    except IntegrityError:
        flash('Tu as déjà voté pour ce jeu ou identifiant de jeu invalide.', 'error')

    return redirect(url_for('lan_games'))


@app.route('/lan/jeux/proposer')
@login_required
def lan_games_proposal() -> Union[str, Response]:
    if not current_user.can_access_lan_section:
        flash('Désolé, tu ne fait pas partie des participants à la LAN.', 'error')

        return redirect(url_for('home'))

    form = LanGamesProposalSearchForm(request.args, meta={'csrf': False})
    validated = len(request.args) > 0 and form.validate()

    games = []

    if validated:
        games = db.session.execute(
            search(
                sa.select(Game)
                .options(
                    sa_orm.selectinload(Game.proposal).selectinload(LanGameProposal.user)
                )
                .limit(20)
                .order_by(
                    sa.desc(
                        sa.func.ts_rank_cd(Game.search_vector, sa.func.parse_websearch(form.terms.data), 2)
                    )
                ),
                form.terms.data
            )
        ).scalars().all()

    return render_template(
        'lan/games_proposal.html',
        form=form,
        validated=validated,
        games=games
    )


@app.route('/lan/jeux/proposer/<int:game_id>')
@login_required
def lan_games_proposal_submit(game_id: int) -> Response:
    if not current_user.can_access_lan_section:
        flash('Désolé, tu ne fait pas partie des participants à la LAN.', 'error')

        return redirect(url_for('home'))

    try:
        game = db.get_or_404(Game, game_id)

        proposal = LanGameProposal()
        proposal.game_id = game_id
        proposal.user_id = current_user.id

        db.session.add(proposal)
        db.session.commit()

        discord.send_message(
            f'**{current_user.display_name}** a proposé un nouveau jeu :',
            [
                {
                    'type': 'rich',
                    'title': game.name,
                    'color': 0xf56b3d,
                    'url': f'https://store.steampowered.com/app/{game.id}',
                    'image': {
                        'url': f'https://cdn.cloudflare.steamstatic.com/steam/apps/{game.id}/capsule_231x87.jpg',
                    }
                }
            ],
            [
                {
                    'type': 1,
                    'components': [
                        {
                            'type': 2,
                            'label': 'Voter !',
                            'style': 5,
                            'url': url_for('lan_games', _external=True),
                        }
                    ]
                }
            ]
        )

        flash('Ta proposition a bien été enregistrée !', 'success')
    except IntegrityError:
        flash('Ce jeu a déjà été proposé.', 'error')
    except NotFound:
        flash('Identifiant de jeu invalide.', 'error')

    return redirect(url_for('lan_games_proposal', **request.args))
