from flask_discord_interactions import Message, Embed, ActionRow, ButtonStyles, Button, Context, Autocomplete, Option
from hub.models import User, Game, VoteType, LanGameProposal, LanGameProposalVote
from hub.pubg import MAPS_NAMES, GAME_MODES_NAMES, MATCH_TYPES_NAMES
from flask_discord_interactions.models.embed import Media, Field
from sqlalchemy_searchable import search, inspect_search_vectors
from app import app, db, discord_interactions
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func as sa_func
from typing import Dict, Literal, List
from flask import url_for, session, g
from urllib.parse import urlencode
from requests import Response
import sqlalchemy.orm as sa_orm
import sqlalchemy as sa
import requests
import secrets

requests = requests.Session()
requests.headers.update({
    'Accept': 'application/json'
})

SCOPES = (
    'identify',
    'guilds.members.read'
)

API_BASE_URL = 'https://discord.com/api'

EMBEDS_COLOR = 0xf56b3d


def generate_authorize_url() -> str:
    session['oauth2_state'] = secrets.token_urlsafe(16)

    discord_qs = urlencode({
        'client_id': app.config['DISCORD_CLIENT_ID'],
        'redirect_uri': url_for('login_callback', _external=True, _scheme=app.config['PREFERRED_URL_SCHEME']),
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'state': session['oauth2_state'],
    })

    return 'https://discord.com/oauth2/authorize?' + discord_qs


def get_oauth_token(code: str) -> Response:
    return requests.post(
        f'{API_BASE_URL}/oauth2/token',
        data={
            'client_id': app.config['DISCORD_CLIENT_ID'],
            'client_secret': app.config['DISCORD_CLIENT_SECRET'],
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': url_for('login_callback', _external=True, _scheme=app.config['PREFERRED_URL_SCHEME']),
        }
    )


def get_membership_info(token: Dict) -> Response:
    return requests.get(
        '{API_BASE_URL}/users/@me/guilds/{DISCORD_GUILD_ID}/member'.format(API_BASE_URL=API_BASE_URL, **app.config),
        headers={
            'Authorization': '{token_type} {access_token}'.format(**token),
        }
    )


def can_send_messages() -> bool:
    return app.config['DISCORD_LAN_CHANNEL_ID'] and app.config['DISCORD_BOT_TOKEN']


@discord_interactions.custom_handler('top')
def _handle_top_button(ctx: Context) -> Message:
    if g.lan_games_status == 'disabled':
        return Message(
            'On ne choisis pas encore les jeux pour la LAN !',
            ephemeral=True
        )

    proposals = db.session.execute(
        sa.select(LanGameProposal)
        .options(
            sa_orm.selectinload(LanGameProposal.game),
            sa_orm.selectinload(LanGameProposal.votes)
        )
    ).scalars().all()

    lan_participants_count = db.session.execute(
        sa.select(sa_func.count('*')).select_from(User)
        .where(User.is_lan_participant == True)
    ).scalar()

    for proposal in proposals:
        proposal.is_essential = proposal.votes_count(VoteType.YES) == lan_participants_count

    proposals.sort(key=lambda p: p.score, reverse=True)

    proposals = proposals[:app.config['TOP_LAN_GAME_PROPOSALS']]

    return Message(
        'Voici le **top {TOP_LAN_GAME_PROPOSALS}** actuel des jeux proposés :'.format(**app.config),
        embed=Embed(
            color=EMBEDS_COLOR,
            fields=[
                Field(
                    name='{}{}'.format(
                        '⭐️ ' if proposal.is_essential else '',
                        proposal.game.name
                    ),
                    value='  '.join([
                        '{} {}'.format(
                            _vote_type_emoji(vote_type),
                            proposal.votes_count(vote_type),
                        ) for vote_type in VoteType
                    ]),
                    inline=True
                ) for proposal in proposals
            ]
        ),
        components=[
            ActionRow(
                components=[
                    Button(
                        style=ButtonStyles.LINK,
                        label='Voir tous les jeux',
                        url=url_for('lan_games_vote', _external=True),
                    )
                ]
            )
        ]
    )


@discord_interactions.custom_handler('vote')
def _handle_vote_button(ctx: Context, game_id: int, vote_type: Literal['YES', 'NEUTRAL', 'NO']) -> Message:
    user = db.session.get(User, ctx.author.id)

    if not user:
        message = 'Tu n\'a pas encore de compte sur notre intranet. Crée-le ici {} et rééssaye. Tu peux également voter ici {}.'.format(
            url_for('login', _external=True),
            url_for('lan_games_vote', _external=True),
        )
    elif user.must_relogin:
        message = 'Merci de te reconnecter sur notre intranet puis réessaye : {} (tu ne devras effectuer cette action qu\'une fois).'.format(
            url_for('login', _external=True)
        )
    elif not user.is_lan_participant:
        message = 'Désolé, tu ne fais pas partie des participants à la LAN.'
    elif g.lan_games_status == 'disabled':
        message = 'On ne choisis pas encore les jeux pour la LAN, revient plus tard !'
    elif g.lan_games_status == 'read_only':
        message = 'Trop tard, la date de la LAN approche, les propositions et votes sont figés !'
    else:
        try:
            LanGameProposalVote.vote(user, game_id, VoteType(vote_type))

            db.session.commit()

            message = 'A voté !'
        except ValueError:
            message = 'Type de vote invalide.'
        except IntegrityError:
            message = 'Identifiant de jeu invalide.'

    return Message(
        message,
        ephemeral=True
    )


@discord_interactions.command(
    'proposer',
    'Permet de proposer un jeu pour notre LAN.',
    annotations={
        'jeu': 'Le jeu que tu souhaites proposer (les jeux déjà proposés sont exclus)',
    }
)
def submit_game_proposal_command(ctx: Context, jeu: Autocomplete(int)) -> Message:
    user = db.session.get(User, ctx.author.id)

    if not user:
        message = 'Tu n\'a pas encore de compte sur notre intranet. Crée-le ici {} et rééssaye. Tu peux également proposer ici {}.'.format(
            url_for('login', _external=True),
            url_for('lan_games_proposal', _external=True),
        )
    elif user.must_relogin:
        message = 'Merci de te reconnecter sur notre intranet puis réessaye : {} (tu ne devras effectuer cette action qu\'une fois).'.format(
            url_for('login', _external=True)
        )
    elif not user.is_lan_participant:
        message = 'Désolé, tu ne fais pas partie des participants à la LAN.'
    elif g.lan_games_status == 'disabled':
        message = 'On ne choisis pas encore les jeux pour la LAN, revient plus tard !'
    elif g.lan_games_status == 'read_only':
        message = 'Trop tard, la date de la LAN approche, les propositions et votes sont figés !'
    else:
        try:
            proposal = LanGameProposal()
            proposal.game_id = jeu
            proposal.user_id = user.id

            db.session.add(proposal)

            LanGameProposalVote.vote(user, jeu, VoteType.YES)

            db.session.commit()

            if can_send_messages():
                send_proposal_message(
                    user,
                    db.get_or_404(Game, jeu)
                )

            message = 'Merci pour ta proposition !'
        except IntegrityError:
            message = 'Ce jeu a déjà été proposé (ou identifiant de jeu invalide).'
        except NotFound:
            message = 'Identifiant de jeu invalide.'

    return Message(
        message,
        ephemeral=True
    )


@submit_game_proposal_command.autocomplete()
def more_autocomplete_handler(ctx: Context, jeu: Option = None) -> List[Dict]:
    if jeu or not jeu.focused or not jeu.value:
        return []

    games = db.session.execute(
        search(
            sa.select(Game.id, Game.name)
            .outerjoin(LanGameProposal)
            .filter(LanGameProposal.id == None)
            .limit(25)
            .order_by(
                sa.desc(
                    sa.func.ts_rank_cd(inspect_search_vectors(Game)[0], sa.func.parse_websearch(jeu.value), 2)
                )
            ),
            jeu.value,
            regconfig=sa.cast('english_nostop', postgresql.REGCONFIG)
        )
    ).scalars().all()

    return [
        {
            'value': game.id,
            'name': game.name
        } for game in games
    ]


def send_proposal_message(user: User, game: Game) -> None:
    components = [
        Button(
            style=ButtonStyles.PRIMARY,
            custom_id=[_handle_vote_button, game.id, vote_type.value],
            emoji={
                'name': _vote_type_emoji(vote_type),
            }
        ) for vote_type in VoteType
    ]

    components.extend([
        Button(
            style=ButtonStyles.SECONDARY,
            custom_id=_handle_top_button,
            label='Voir le top {TOP_LAN_GAME_PROPOSALS}'.format(**app.config),
        ),
        Button(
            style=ButtonStyles.LINK,
            label='Voir tous les jeux',
            url=url_for('lan_games_vote', _external=True),
        )
    ])

    data, content_type = Message(
        f'**{user.display_name}** a proposé un nouveau jeu :',
        embed=Embed(
            title=game.name,
            color=EMBEDS_COLOR,
            url=game.url,
            image=Media(game.image_url)
        ),
        components=[
            ActionRow(
                components=components
            )
        ]
    ).encode(True)

    response = _send_message(app.config['DISCORD_LAN_CHANNEL_ID'], data, content_type)

    json = response.json()

    _start_thread(
        app.config['DISCORD_LAN_CHANNEL_ID'],
        json.get('id'),
        game.name
    )


def send_chicken_dinner_message(
    participants_rank: int,
    total_teams: int,
    match_id: str,
    map_id: str,
    game_mode_id: str,
    match_type_id: str,
    duration: int,
    participants: List[Dict],
    other_participants_count: int
) -> Response:
    def _participant_name(participant: Dict) -> str:
        return '[{0}](https://pubg.sh/{0}/{1}/{2})'.format(
            participant['attributes']['stats']['name'],
            participant['attributes']['shardId'],
            match_id
        )

    last_participant = None
    participants_for_player_names = participants

    if len(participants) > 1 and other_participants_count == 0:
        last_participant = participants[-1]
        participants_for_player_names = participants[:-1]

    participants_names = ', '.join([
        _participant_name(participant) for participant in participants_for_player_names
    ])

    if last_participant:
        participants_names += ' et ' + _participant_name(last_participant)
    elif other_participants_count > 0:
        participants_names += f' et {other_participants_count} {"autres joueurs" if other_participants_count > 1 else "autre joueur"}'

    pluralize = len(participants) > 1

    participants_names_list = [
        participant['attributes']['stats']['name'] for participant in participants
    ]

    map_name = MAPS_NAMES.get(map_id, '?')
    game_mode_name = GAME_MODES_NAMES.get(game_mode_id, '?')
    match_type_name = MATCH_TYPES_NAMES.get(match_type_id, '?')

    won_term = secrets.choice(['top 1', 'Chicken Dinner'])

    duration_minutes, duration_seconds = divmod(duration, 60)
    duration_humanized = f'{duration_minutes} {"minutes" if duration_minutes > 1 else "minute"}'

    if duration_seconds > 0:
        duration_humanized += f' et {duration_seconds} {"secondes" if duration_seconds > 1 else "seconde"}'

    if participants_rank == 1:
        emojis = ['🥇', '🐔', '🍗', '🏆', '🍀']

        contents = [
            f'Les parents de {participants_names} peuvent enfin être fiers !',
            f'On y croyait vraiment plus, {participants_names} !',
            f'{participants_names} {"ont" if pluralize else "a"} brillé (pour une fois) !',
            f'Dieu existe et le prouve à travers {participants_names} !',
            f'{participants_names} {"dormiront" if pluralize else "dormira"} l\'esprit tranquille ce soir !',
            f'C\'est {participants_names} qui {"régalent" if pluralize else "régale"} ce soir !',
            f'La zone est pacifiée grâce à {participants_names} !',
            f'C\'était mal barré comme d\'habitude, mais le skill (plus probablement la chance) a fait que {participants_names} {"finissent" if pluralize else "finisse"} sur un {won_term} !',
            f'Vous ne devinerez jamais comment ce {won_term} hallucinant a été atteint par {participants_names} !',
            f'Et ben voilà {participants_names}, {duration_humanized} ! C\'était pas si compliqué !',
            f'Les planètes se sont enfin alignées pour {participants_names} !',
            f'{participants_names} : chaque tirage au sort a {"ses" if pluralize else "son"} {"gagnants" if pluralize else "gagnant"} après tout !',
            f'Contre toute attente (et probablement grâce à un bug), {participants_names} {"inscrivent" if pluralize else "inscrit"} enfin un {won_term} !',
            f'{participants_names} {"marquent" if pluralize else "marque"} un {won_term} ?!? Il est vrai que même une horloge cassée donne l\'heure juste deux fois par jour !',
        ]

        if 'Pepsite' in participants_names_list:
            contents.extend([
                f'{participants_names} {"ont" if pluralize else "a"} atteint le {won_term}, heureusement que (pour une fois) la conduite de Pepsite n\'a pas laissé à désirer !',
                f'{won_term.capitalize()} pour {participants_names}, {"véhiculés" if pluralize else "véhiculé"} par Pepsite qui a enfin réussit à éviter tous les arbres et rochers sur sa route, son assurance auto le remercie pour cet exploit !',
            ])

        if 'DrMastock' in participants_names_list:
            contents.extend([
                f'{won_term.capitalize()} pour {participants_names}, sûrement grâce à la x8 de DrMastock trouvée au dernier moment !',
                f'{won_term.capitalize()} pour {participants_names}, la lunette x8 tant réclamée par DrMastock durant la partie lui a ouvert la vision pour le tir décisif !',
            ])

        if match_type_id == 'airoyale':
            contents.extend([
                f'Oui mais {participants_names} : tranquille, c\'était en casu !',
                f'Impressionnant ce {won_term} contre des bots, {participants_names} !',
            ])

        images = [
            'https://pbs.twimg.com/media/EXfqIngWsAA6gBq.jpg',
            'https://i.imgur.com/M33pWNM.png',
            'https://c.tenor.com/vOKwPz3lifIAAAAC/tenor.gif',
            'https://media.toucharger.com/web/toucharger/upload/image_domain/7/5/75657/75657.gif',
            'https://c.tenor.com/z04usSAGgJwAAAAd/tenor.gif',
            'https://c.tenor.com/XYvg-iC6PT4AAAAC/tenor.gif',
            'https://c.tenor.com/fit861DxTeQAAAAC/tenor.gif',
            'https://c.tenor.com/6XA-L01v3RQAAAAC/tenor.gif',
            'https://c.tenor.com/D8CKeWcZ4noAAAAC/tenor.gif',
            'https://c.tenor.com/7hFAPpCnMJ8AAAAC/tenor.gif',
            'https://c.tenor.com/1ml7iQMOEXMAAAAd/tenor.gif',
            'https://c.tenor.com/xq1W-BtokTEAAAAd/tenor.gif',
        ]
    elif participants_rank in (2, 3):
        emojis = ['😐']

        if participants_rank == 2:
            emojis.extend(['🥈'])
        elif participants_rank == 3:
            emojis.extend(['🥉'])

        contents = [
            f'Ah là là {participants_names}, il manquait juste un tout petit peu de cette chose (le skill) pour atteindre le {won_term} !',
            f'"Peut mieux faire", exactement ce qu\'il y avait écrit jadis sur {"les bulletins" if pluralize else "le bulletin"} de {participants_names} !',
            f'Tristesse pour {participants_names}, {duration_humanized} de jeu pour échouer si proche du {won_term} !',
        ]

        if match_type_id == 'airoyale':
            contents.extend([
                f'Comment ça {participants_names} ? Échouer si près du {won_term} contre des bots !',
            ])

        images = [
            'https://c.tenor.com/pE_YL3nfwZsAAAAd/tenor.gif',
            'https://c.tenor.com/YaDhkmcINSsAAAAC/tenor.gif',
            'https://c.tenor.com/4VPgpSl9Pm8AAAAC/tenor.gif',
            'https://c.tenor.com/EI6kCtkMm6sAAAAC/tenor.gif',
            'https://c.tenor.com/Twp3GsrGEYIAAAAC/tenor.gif',
        ]

        if participants_rank == 2:
            images.extend({
                'https://c.tenor.com/mNDuJOeUqgEAAAAC/tenor.gif',
            })
    else:
        emojis = ['🤦‍♂️', '🤕️', '🚮', '🤡', '☠️', '💩', '⚰️']

        contents = [
            f'Toucher le fond : c\'est tout ce que {participants_names} {"ont" if pluralize else "a"} pu faire.',
            f'{participants_names} {"ont" if pluralize else "a"} brillé par {"leur" if pluralize else "sa"} médiocrité.',
            f'Tout ce qu\'il ne fallait pas faire, {participants_names} l\'{"ont" if pluralize else "a"} fait.',
            f'{participants_names} {"étaient" if pluralize else "était"} loin, très loin du {won_term}.',
            f'{duration_humanized} : c\'était très rapide cette fois pour {participants_names}.',
            f'{participants_names} : {"vous étiez les maillons faibles" if pluralize else "tu était le maillon faible"}. Au revoir.',
            f'Etait-ce la malchance ? Le manque de skill ? La carte ? Sûrement les trois pour {participants_names}.',
            f'{participants_names} {"ont" if pluralize else "a"} un talent certain. Celui d\'explorer les bas-fonds du classement avec autant de constance.',
            f'{participants_names}, {"vous avez" if pluralize else "tu as"} prouvé que la défaite peut être une forme d\'art. Bravo pour cette performance.',
            f'{participants_names} {"ont" if pluralize else "a"} terminé dernier. Au moins, il n\'y a qu\'une seule direction possible maintenant : vers le haut.',
            f'Purée {participants_names}, {duration_humanized} de jeu, {"vous déconnez" if pluralize else "tu déconnes"}.',
            f'{participants_names} : Jack Bauer {"vous" if pluralize else "te"} regarde l\'air mauvais, {"vous" if pluralize else "toi"} et {"vos" if pluralize else "tes"} {duration_humanized} de temps de jeu.',
        ]

        if 'Pepsite' in participants_names_list:
            contents.extend([
                f'La prochaine fois {participants_names}, ne {"laissez" if pluralize else "laisse"} pas Pepsite conduire.',
            ])

        if match_type_id == 'airoyale':
            contents.extend([
                f'Tous les bots amorphes de la map se sont montrés plus performant que {participants_names}.',
            ])

        images = [
            'https://c.tenor.com/-huJTdSu9PkAAAAd/tenor.gif',
            'https://c.tenor.com/ZFc20z8DItkAAAAC/tenor.gif',
            'https://1.bp.blogspot.com/-0a3fg-fUWdw/T3On8vGgmVI/AAAAAAAAA4A/PJg-1gRMH5Y/s200/bunk-the-wire.gif',
            'https://c.tenor.com/pclCqjkaebQAAAAC/tenor.gif',
            'https://c.tenor.com/bO1zLArkvScAAAAC/tenor.gif',
            'https://c.tenor.com/dNknbuz05okAAAAd/tenor.gif',
            'https://c.tenor.com/yxHvgtplhQUAAAAC/tenor.gif',
            'https://c.tenor.com/7Blzpyg7858AAAAC/tenor.gif',
            'https://c.tenor.com/htYX1pCbv78AAAAC/tenor.gif',
            'https://c.tenor.com/IBB_J7rODV0AAAAC/tenor.gif',
            'https://c.tenor.com/U6tMT8K4cZIAAAAC/tenor.gif',
        ]

    data, content_type = Message(
        content=secrets.choice(contents),
        embed=Embed(
            title=f'🗺️ {map_name} 🕹️ {match_type_name} 👥 {game_mode_name}',
            description='{} Top {} sur {}'.format(
                secrets.choice(emojis),
                participants_rank,
                total_teams
            ),
            color=EMBEDS_COLOR,
            image=Media(secrets.choice(images)),
            fields=[
                Field(
                    name=participant['attributes']['stats']['name'],
                    value='💀 {} 🆘 {} 🤕 {:.0f}'.format(
                        participant['attributes']['stats']['kills'],
                        participant['attributes']['stats']['assists'],
                        participant['attributes']['stats']['damageDealt']
                    ),
                    inline=True
                ) for participant in participants
            ]
        )
    ).encode(True)

    return _send_message(app.config['DISCORD_PUBG_CHANNEL_ID'], data, content_type)


def _send_message(channel_id: int, data: Dict, content_type: str) -> Response:
    return requests.post(
        '{API_BASE_URL}/channels/{channel_id}/messages'.format(API_BASE_URL=API_BASE_URL, channel_id=channel_id, **app.config),
        data=data,
        headers={
            'Content-Type': content_type,
            'Authorization': 'Bot {DISCORD_BOT_TOKEN}'.format(**app.config),
        }
    )


def _start_thread(channel_id: int, message_id: int, name: str) -> Response:
    return requests.post(
        '{API_BASE_URL}/channels/{channel_id}/messages/{message_id}/threads'.format(API_BASE_URL=API_BASE_URL, channel_id=channel_id, message_id=message_id, **app.config),
        json={
            'name': name,
        },
        headers={
            'Authorization': 'Bot {DISCORD_BOT_TOKEN}'.format(**app.config),
        }
    )


def _vote_type_emoji(vote_type: VoteType) -> str:
    if vote_type == vote_type.YES:
        return '👍'

    if vote_type == vote_type.NEUTRAL:
        return '😐'

    if vote_type == vote_type.NO:
        return '👎'

    return ''
