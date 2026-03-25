from flask_babel import format_currency

from hub.models import User, Game, VoteType, LanGameProposal, LanGameProposalVote, LanAccommodationProposal, LanAccommodationProposalVote
from flask_discord_interactions import Message, Embed, ActionRow, ButtonStyles, Button, Context, Autocomplete, Option
from flask_discord_interactions.models.embed import Media, Field, Footer
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


def can_send_lan_messages() -> bool:
    return app.config['DISCORD_BOT_TOKEN'] and app.config['DISCORD_LAN_CHANNEL_ID']


def can_send_organizer_messages() -> bool:
    return app.config['DISCORD_BOT_TOKEN'] and app.config['DISCORD_LAN_ORGANIZER_CHANNEL_ID']


def _handle_top_games(ctx: Context) -> Message:
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


@discord_interactions.custom_handler('top')
def _handle_game_top_button(ctx: Context) -> Message:
    return _handle_top_games(ctx)


@discord_interactions.custom_handler('vote-game')
def _handle_game_vote_button(ctx: Context, game_id: int, vote_type: Literal['YES', 'NEUTRAL', 'NO']) -> Message:
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
        message = 'Trop tard, la date de la LAN approche, les jeux principaux ont été choisis !'
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


@discord_interactions.custom_handler('vote-accommodation')
def _handle_accommodation_vote_button(ctx: Context, accommodation_proposal_id: int, vote_type: Literal['YES', 'NEUTRAL', 'NO']) -> Message:
    user = db.session.get(User, ctx.author.id)

    if not user:
        message = 'Tu n\'a pas encore de compte sur l\'intranet. Crée-le ici {} et rééssaye. Tu peux également voter ici {}.'.format(
            url_for('login', _external=True),
            url_for('lan_accommodations_vote', _external=True),
        )
    elif user.must_relogin:
        message = 'Merci de te reconnecter sur l\'intranet puis réessaye : {} (tu ne devras effectuer cette action qu\'une fois).'.format(
            url_for('login', _external=True)
        )
    elif not user.is_lan_organizer:
        message = 'Désolé, tu ne fais pas partie des organisateurs de la LAN.'
    elif g.lan_accommodations_status == 'disabled':
        message = 'On ne choisis pas encore le logement pour la LAN, revient plus tard !'
    elif g.lan_accommodations_status == 'read_only':
        message = 'Trop tard, le logement a été choisi !'
    else:
        try:
            LanAccommodationProposalVote.vote(user, accommodation_proposal_id, VoteType(vote_type))

            db.session.commit()

            message = 'A voté !'
        except ValueError:
            message = 'Type de vote invalide.'
        except IntegrityError:
            message = 'Identifiant de logement invalide.'

    return Message(
        message,
        ephemeral=True
    )


@discord_interactions.command(
    'proposer',
    'Propose un jeu pour notre LAN annuelle.',
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
        message = 'Trop tard, la date de la LAN approche, les jeux principaux ont été choisis !'
    else:
        try:
            proposal = LanGameProposal()
            proposal.game_id = jeu
            proposal.user_id = user.id

            db.session.add(proposal)

            LanGameProposalVote.vote(user, jeu, VoteType.YES)

            db.session.commit()

            if can_send_lan_messages():
                send_game_proposal_message(
                    user,
                    db.session.get(Game, jeu)
                )

            message = 'Merci pour ta proposition !'
        except IntegrityError:
            message = 'Ce jeu a déjà été proposé (ou identifiant de jeu invalide).'

    return Message(
        message,
        ephemeral=True
    )


@submit_game_proposal_command.autocomplete()
def submit_game_proposal_command_autocomplete(ctx: Context, jeu: Option = None) -> List[Dict]:
    if not jeu or not jeu.focused or not jeu.value:
        return []

    games = db.session.execute(
        search(
            sa.select(Game.id, Game.name)
            .outerjoin(LanGameProposal)
            .filter(LanGameProposal.game_id == None)
            .limit(25)
            .order_by(
                sa.desc(
                    sa.func.ts_rank_cd(inspect_search_vectors(Game)[0], sa.func.parse_websearch(jeu.value), 2)
                )
            ),
            jeu.value,
            regconfig=sa.cast('english_nostop', postgresql.REGCONFIG)
        )
    ).all()

    return [
        {
            'value': game.id,
            'name': game.name
        } for game in games
    ]


@discord_interactions.command(
    'top',
    'Affiche le top {TOP_LAN_GAME_PROPOSALS} actuel des jeux proposés.'.format(**app.config)
)
def top_games_command(ctx: Context) -> Message:
    return _handle_top_games(ctx)


def send_game_proposal_message(user: User, game_proposal: LanGameProposal) -> None:
    components = [
        Button(
            style=ButtonStyles.PRIMARY,
            custom_id=[_handle_game_vote_button, game_proposal.game.id, vote_type.value],
            emoji={
                'name': _vote_type_emoji(vote_type),
            }
        ) for vote_type in VoteType
    ]

    components.extend([
        Button(
            style=ButtonStyles.SECONDARY,
            custom_id=_handle_game_top_button,
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
            title=game_proposal.game.name,
            color=EMBEDS_COLOR,
            url=game_proposal.game.url,
            image=Media(game_proposal.game.image_url),
            footer=Footer('👤 Un seul détenteur suffit potentiellement !') if game_proposal.game.single_owner_enough else None
        ),
        components=[
            ActionRow(
                components=components
            )
        ]
    ).encode(True)

    if game_proposal.message_id:
        _update_message(app.config['DISCORD_LAN_CHANNEL_ID'], game_proposal.message_id, data, content_type)
    else:
        message_id = _send_message(app.config['DISCORD_LAN_CHANNEL_ID'], data, content_type).json().get('id')

        game_proposal.message_id = message_id

        db.session.add(game_proposal)

        db.session.commit()

        _start_thread(
            app.config['DISCORD_LAN_CHANNEL_ID'],
            message_id,
            game_proposal.game.name
        )


def send_accommodation_proposal_message(user: User, accommodation_proposal: LanAccommodationProposal) -> None:
    components = [
        Button(
            style=ButtonStyles.PRIMARY,
            custom_id=[_handle_accommodation_vote_button, accommodation_proposal.id, vote_type.value],
            emoji={
                'name': _vote_type_emoji(vote_type),
            }
        ) for vote_type in VoteType
    ]

    components.extend([
        Button(
            style=ButtonStyles.LINK,
            label=accommodation_proposal.location_name,
            url=accommodation_proposal.location_url,
        ),
        Button(
            style=ButtonStyles.LINK,
            label='Voir tous les logements',
            url=url_for('lan_accommodations_vote', _external=True),
        ),
    ])

    fields = [
        Field(
            name='Prix total',
            value=format_currency(accommodation_proposal.total_price, 'EUR'),
            inline=True
        ),
        Field(
            name='Chambres',
            value=str(accommodation_proposal.bedrooms),
            inline=True
        ),
        Field(
            name='Lits simples',
            value=str(accommodation_proposal.single_beds),
            inline=True
        ),
        Field(
            name='Lits doubles',
            value=str(accommodation_proposal.twin_beds),
            inline=True
        ),
    ]

    if accommodation_proposal.large_tables is not None:
        fields.append(
            Field(
                name='Grandes tables',
                value=str(accommodation_proposal.large_tables),
                inline=True
            )
        )

    if accommodation_proposal.has_fiber is not None:
        fields.append(
            Field(
                name='Fibre optique ?',
                value=':white_check_mark:' if accommodation_proposal.has_fiber else ':x:',
                inline=True
            )
        )

    if accommodation_proposal.has_private_parking is not None:
        fields.append(
            Field(
                name='Parking privé ?',
                value=':white_check_mark:' if accommodation_proposal.has_private_parking else ':x:',
                inline=True
            )
        )

    data, content_type = Message(
        f'**{user.display_name}** a proposé un nouveau logement :',
        embed=Embed(
            title=accommodation_proposal.title,
            description=accommodation_proposal.notes,
            color=EMBEDS_COLOR,
            url=accommodation_proposal.listing_url,
            image=Media(accommodation_proposal.photo_url),
            fields=fields
        ),
        components=[
            ActionRow(
                components=components
            )
        ]
    ).encode(True)

    if accommodation_proposal.message_id:
        _update_message(app.config['DISCORD_LAN_ORGANIZER_CHANNEL_ID'], accommodation_proposal.message_id, data, content_type)
    else:
        message_id = _send_message(app.config['DISCORD_LAN_ORGANIZER_CHANNEL_ID'], data, content_type).json().get('id')

        accommodation_proposal.message_id = message_id

        db.session.add(accommodation_proposal)

        db.session.commit()

        _start_thread(
            app.config['DISCORD_LAN_ORGANIZER_CHANNEL_ID'],
            message_id,
            accommodation_proposal.title
        )


def _send_message(channel_id: int, data: Dict, content_type: str) -> Response:
    return requests.post(
        '{API_BASE_URL}/channels/{channel_id}/messages'.format(API_BASE_URL=API_BASE_URL, channel_id=channel_id, **app.config),
        data=data,
        headers={
            'Content-Type': content_type,
            'Authorization': 'Bot {DISCORD_BOT_TOKEN}'.format(**app.config),
        }
    )


def _update_message(channel_id: int, message_id: int, data: Dict, content_type: str) -> Response:
    return requests.patch(
        '{API_BASE_URL}/channels/{channel_id}/messages/{message_id}'.format(API_BASE_URL=API_BASE_URL, channel_id=channel_id, message_id=message_id, **app.config),
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
