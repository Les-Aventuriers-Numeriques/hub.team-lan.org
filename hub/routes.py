from hub.forms import LanGamesProposalSearchForm, LanGamesSettingsForm, LanGamesVoteFilterForm
from hub.models import User, Game, LanGameProposal, LanGameProposalVote, VoteType, Setting
from flask import render_template, redirect, url_for, flash, session, request, g
from flask_login import login_required, current_user, logout_user, login_user
from sqlalchemy_searchable import search, inspect_search_vectors
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import NotFound
from sqlalchemy import func as sa_func
from werkzeug import Response
from functools import wraps
from typing import Union
from app import app, db
import sqlalchemy.orm as sa_orm
import hub.discord as discord
import sqlalchemy as sa


def to_home_if_authenticated(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('home'))

        return f(*args, **kwargs)

    return decorated


def to_home_if_cannot_access_lan_section(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_lan_participant:
            flash('Désolé, tu ne fais pas partie des participants à la LAN.', 'error')

            return redirect(url_for('home'))

        if g.lan_games_status == 'disabled':
            flash('On ne choisis pas encore les jeux pour la LAN, revient plus tard !', 'error')

            return redirect(url_for('home'))

        return f(*args, **kwargs)

    return decorated


def to_lan_games_vote_if_lan_section_read_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.lan_games_status == 'read_only':
            flash('Trop tard, la date de la LAN approche, les propositions et votes sont figés !', 'error')

            return redirect(url_for('lan_games_vote'))

        return f(*args, **kwargs)

    return decorated


def to_home_if_not_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Tu n\'as pas accès à ceci.', 'error')

            return redirect(url_for('home'))

        return f(*args, **kwargs)

    return decorated


def logout_if_must_relogin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.must_relogin:
            logout_user()

            flash('Merci de te reconnecter.', 'error')

            return redirect(url_for('login'))

        return f(*args, **kwargs)

    return decorated


@app.route('/connexion')
@to_home_if_authenticated
def login() -> Union[str, Response]:
    return render_template(
        'login.html',
        login_discord_url=discord.generate_authorize_url()
    )


@app.route('/connexion/callback')
@to_home_if_authenticated
def login_callback() -> Union[str, Response]:
    error = request.args.get('error')

    if error:
        error_description = request.args.get('error_description', 'aucune')

        flash(f'Erreur lors de la connexion avec Discord (code : {error} ; description : {error_description}).', 'error')

        return redirect(url_for('login'))

    state = request.args.get('state')
    code = request.args.get('code')

    if state != session.get('oauth2_state') or not code:
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

    is_member = str(app.config['DISCORD_MEMBER_ROLE_ID']) in user_roles
    is_lan_participant = str(app.config['DISCORD_LAN_PARTICIPANT_ROLE_ID']) in user_roles
    is_admin = str(app.config['DISCORD_ADMIN_ROLE_ID']) in user_roles
    has_any_role = is_member or is_lan_participant or is_admin

    user_info = membership_info.get('user', {})

    discord_id = user_info.get('id')

    user = db.session.get(User, discord_id)
    is_new_user = not user

    if is_new_user:
        if not has_any_role:
            flash('Tu n\'as pas l\'autorisation d\'accéder à notre intranet.', 'error')

            return redirect(url_for('login'))

        user = User()
        user.id = discord_id

    user.display_name = membership_info.get('nick') or user_info.get('global_name') or user_info.get('username')

    member_avatar_hash = membership_info.get('avatar')
    user_avatar_hash = user_info.get('avatar')

    if member_avatar_hash:
        guild_id = app.config['DISCORD_GUILD_ID']

        user.avatar_url = f'https://cdn.discordapp.com/guilds/{guild_id}/users/{discord_id}/avatars/{member_avatar_hash}.png'
    elif user_avatar_hash:
        user.avatar_url = f'https://cdn.discordapp.com/avatars/{discord_id}/{user_avatar_hash}.png'

    user.is_member = is_member
    user.is_lan_participant = is_lan_participant
    user.is_admin = is_admin
    user.must_relogin = False

    db.session.add(user)
    db.session.commit()

    session.pop('oauth2_state', None)

    if not has_any_role:
        flash('Désolé, tu n\'as plus l\'autorisation d\'accéder à notre intranet.', 'error')

        return redirect(url_for('login'))

    login_user(user, remember=True)

    flash('{} {} !'.format('Bienvenue' if is_new_user else 'Content de te revoir', user.display_name), 'success')

    return redirect(session.pop('next', url_for('home')))


@app.route('/deconnexion')
@login_required
def logout() -> Response:
    flash(f'À plus {current_user.display_name} !', 'success')

    logout_user()

    return redirect(url_for('login'))


@app.route('/')
@login_required
@logout_if_must_relogin
def home() -> str:
    return render_template('home.html')


@app.route('/lan/jeux/voter')
@login_required
@logout_if_must_relogin
@to_home_if_cannot_access_lan_section
def lan_games_vote() -> Union[str, Response]:
    form = LanGamesVoteFilterForm(request.args, meta={'csrf': False})
    validated = len(request.args) > 0 and form.validate()

    proposals = db.session.execute(
        sa.select(LanGameProposal)
        .options(
            sa_orm.selectinload(LanGameProposal.game),
            sa_orm.selectinload(LanGameProposal.user),
            sa_orm.selectinload(LanGameProposal.votes)
        )
    ).scalars().all()

    if validated and form.filter.data:
        lan_participants_count = db.session.execute(
            sa.select(sa_func.count('*')).select_from(User)
            .where(User.is_lan_participant == True)
        ).scalar()

        def _voted(proposal: LanGameProposal) -> bool:
            return current_user.id in [
                vote.user_id for vote in proposal.votes
            ]

        def _not_voted(proposal: LanGameProposal) -> bool:
            return not _voted(proposal)

        def _all_voted(proposal: LanGameProposal) -> bool:
            return len(proposal.votes) == lan_participants_count

        def _not_all_voted(proposal: LanGameProposal) -> bool:
            return not _all_voted(proposal)

        filter_func = None

        if form.filter.data == 'voted':
            filter_func = _voted
        elif form.filter.data == 'not-voted':
            filter_func = _not_voted
        elif form.filter.data == 'all-voted':
            filter_func = _all_voted
        elif form.filter.data == 'not-all-voted':
            filter_func = _not_all_voted

        if filter_func:
            proposals = [
                proposal for proposal in proposals if filter_func(proposal)
            ]

    proposals.sort(key=lambda p: p.score, reverse=True)

    return render_template(
        'lan/games.html',
        form=form,
        validated=validated,
        proposals=proposals,
        VoteType=VoteType
    )


@app.route('/lan/jeux/voter/<int(signed=True):game_id>/<any({}):vote_type>'.format(VoteType.cslist()))
@login_required
@logout_if_must_relogin
@to_home_if_cannot_access_lan_section
@to_lan_games_vote_if_lan_section_read_only
def lan_games_proposal_vote(game_id: int, vote_type: str) -> Response:
    anchor = None

    try:
        LanGameProposalVote.vote(current_user, game_id, VoteType(vote_type))

        db.session.commit()

        anchor = f'g={game_id}'
    except IntegrityError:
        flash('Identifiant de jeu invalide.', 'error')

    return redirect(url_for('lan_games_vote', filter=request.args.get('filter'), _anchor=anchor))


@app.route('/lan/jeux/proposer')
@login_required
@logout_if_must_relogin
@to_home_if_cannot_access_lan_section
@to_lan_games_vote_if_lan_section_read_only
def lan_games_proposal() -> Union[str, Response]:
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
                .limit(24)
                .order_by(
                    sa.desc(
                        sa.func.ts_rank_cd(inspect_search_vectors(Game)[0], sa.func.parse_websearch(form.terms.data), 2)
                    )
                ),
                form.terms.data,
                regconfig=sa.cast('english_nostop', postgresql.REGCONFIG)
            )
        ).scalars().all()

    return render_template(
        'lan/games_proposal.html',
        form=form,
        validated=validated,
        games=games
    )


@app.route('/lan/jeux/proposer/<int(signed=True):game_id>')
@login_required
@logout_if_must_relogin
@to_home_if_cannot_access_lan_section
@to_lan_games_vote_if_lan_section_read_only
def lan_games_proposal_submit(game_id: int) -> Response:
    anchor = None

    try:
        proposal = LanGameProposal()
        proposal.game_id = game_id
        proposal.user_id = current_user.id

        db.session.add(proposal)
        db.session.commit()

        if discord.can_send_messages():
            discord.send_proposal_message(
                current_user,
                db.get_or_404(Game, game_id)
            )

        anchor = f'g={game_id}'
    except IntegrityError:
        flash('Ce jeu a déjà été proposé (ou identifiant de jeu invalide).', 'error')
    except NotFound:
        flash('Identifiant de jeu invalide.', 'error')

    return redirect(url_for('lan_games_proposal', **request.args, _anchor=anchor))


@app.route('/admin/utilisateurs')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_users() -> Union[str, Response]:
    users = db.session.execute(
        sa.select(User).order_by(User.display_name.asc())
    ).scalars().all()

    return render_template(
        'admin/users.html',
        users=users
    )


@app.route('/admin/utilisateurs/<int:user_id>/supprimer')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_user_delete(user_id: int) -> Response:
    if user_id == current_user.id:
        flash('Tu ne peux pas te supprimer toi-même.', 'error')
    else:
        result = db.session.execute(
            sa.delete(User).where(User.id == user_id)
        )

        db.session.commit()

        if result.rowcount == 1:
            flash('Utilisateur supprimé.', 'success')
        else:
            flash('Identifiant d\'utilisateur invalide.', 'error')

    return redirect(url_for('admin_users'))


@app.route('/admin/utilisateurs/<int:user_id>/forcer-reconnexion')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_user_force_relogin(user_id: int) -> Response:
    result = db.session.execute(
        sa.update(User).where(User.id == user_id).values(must_relogin=True)
    )

    db.session.commit()

    if result.rowcount == 1:
        flash('Utilisateur forcé à se reconnecté.', 'success')
    else:
        flash('Identifiant d\'utilisateur invalide.', 'error')

    return redirect(url_for('admin_users'))


@app.route('/admin/utilisateurs/participants-lan-forcer-reconnexion')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_users_lan_participants_force_relogin() -> Response:
    result = db.session.execute(
        sa.update(User).where(User.is_lan_participant == True).values(must_relogin=True)
    )

    db.session.commit()

    if result.rowcount >= 1:
        flash('Participants à la LAN forcés à se reconnecter.', 'success')
    else:
        flash('Aucun participant à la LAN à forcer à se reconnecter.', 'error')

    return redirect(url_for('admin_users'))


@app.route('/admin/lan/jeux', methods=['GET', 'POST'])
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_lan_games() -> Union[str, Response]:
    proposals = db.session.execute(
        sa.select(LanGameProposal)
        .options(
            sa_orm.selectinload(LanGameProposal.game),
            sa_orm.selectinload(LanGameProposal.user)
        )
    ).scalars().all()

    proposals.sort(key=lambda p: p.game.name)

    form_data = Setting.get(['lan_games_status'])

    form = LanGamesSettingsForm(data=form_data)

    if form.validate_on_submit():
        Setting.set({
            'lan_games_status': form.lan_games_status.data,
        })

        db.session.commit()

        flash('Paramètres enregistrés.', 'success')

        return redirect(url_for('admin_lan_games'))

    return render_template(
        'admin/lan_games.html',
        proposals=proposals,
        form=form
    )


@app.route('/admin/lan/jeux/proposition/<int(signed=True):game_id>/supprimer')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_lan_game_proposal_delete(game_id: int) -> Response:
    result = db.session.execute(
        sa.delete(LanGameProposal).where(LanGameProposal.game_id == game_id)
    )

    db.session.commit()

    if result.rowcount == 1:
        flash('Proposition supprimée.', 'success')
    else:
        flash('Aucune proposition à supprimer.', 'error')

    return redirect(url_for('admin_lan_games'))


@app.route('/admin/lan/jeux/proposition/<int(signed=True):game_id>/supprimer-votes')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_lan_game_proposal_delete_votes(game_id: int) -> Response:
    result = db.session.execute(
        sa.delete(LanGameProposalVote).where(LanGameProposalVote.game_proposal_game_id == game_id)
    )

    db.session.commit()

    if result.rowcount >= 1:
        flash('Votes supprimés.', 'success')
    else:
        flash('Aucun vote à supprimer.', 'error')

    return redirect(url_for('admin_lan_games'))


@app.route('/admin/lan/jeux/propositions/reinitialiser-tout')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_lan_game_proposals_reset_all() -> Response:
    db.session.execute(
        sa.delete(LanGameProposal)
    )

    db.session.commit()

    flash('Propositions et votes réinitialisés.', 'success')

    return redirect(url_for('admin_lan_games'))


@app.route('/admin/lan/jeux/propositions/reinitialiser-votes')
@login_required
@logout_if_must_relogin
@to_home_if_not_admin
def admin_lan_game_proposals_reset_votes() -> Response:
    db.session.execute(
        sa.delete(LanGameProposalVote)
    )

    db.session.commit()

    flash('Votes réinitialisés.', 'success')

    return redirect(url_for('admin_lan_games'))
