from flask_discord_interactions import Message, Embed, ActionRow, ButtonStyles, Button
from hub.models import User, Game, LanGameProposalVoteType, LanGameProposal
from flask_discord_interactions.models.embed import Media, Field
from app import app, db, discord_interactions
from urllib.parse import urlencode
from flask import url_for, session
from typing import Dict, Literal
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
        'redirect_uri': url_for('login_callback', _external=True),
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
            'redirect_uri': url_for('login_callback', _external=True),
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
def _handle_top_button(ctx):
    proposals = db.session.execute(
        sa.select(LanGameProposal)
        .options(
            sa_orm.selectinload(LanGameProposal.game),
            sa_orm.selectinload(LanGameProposal.votes)
        )
    ).scalars().all()

    proposals.sort(key=lambda p: p.score, reverse=True)

    proposals = proposals[:app.config['TOP_LAN_GAME_PROPOSALS']]

    return Message(
        'Voici le **top {TOP_LAN_GAME_PROPOSALS}** actuel des jeux proposés :'.format(**app.config),
        embed=Embed(
            color=EMBEDS_COLOR,
            fields=[
                Field(
                    name=proposal.game.name,
                    value='  '.join([
                        '{} {}'.format(
                            _vote_type_emoji(vote_type),
                            proposal.votes_count(vote_type),
                        ) for vote_type in LanGameProposalVoteType
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


def send_proposal_message(user: User, game: Game) -> Response:
    components = [
        Button(
            style=ButtonStyles.PRIMARY,
            custom_id=_component_custom_id('v', gid=game.id, v=vote_type.value),
            emoji={
                'name': _vote_type_emoji(vote_type),
            }
        ) for vote_type in LanGameProposalVoteType
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
            url=f'https://store.steampowered.com/app/{game.id}',
            image=Media(f'https://cdn.cloudflare.steamstatic.com/steam/apps/{game.id}/capsule_231x87.jpg')
        ),
        components=[
            ActionRow(
                components=components
            )
        ]
    ).encode(True)

    return requests.post(
        '{API_BASE_URL}/channels/{DISCORD_LAN_CHANNEL_ID}/messages'.format(API_BASE_URL=API_BASE_URL, **app.config),
        data=data,
        headers={
            'Content-Type': content_type,
            'Authorization': 'Bot {DISCORD_BOT_TOKEN}'.format(**app.config),
        }
    )


def _vote_type_emoji(vote_type: LanGameProposalVoteType) -> str:
    if vote_type == vote_type.YES:
        return '👍'

    if vote_type == vote_type.NEUTRAL:
        return '😐'

    if vote_type == vote_type.NO:
        return '👎'

    return ''


def _component_custom_id(action: Literal['v', 't'], **params) -> str:
    return urlencode({
        'a': action,
    } | params)
