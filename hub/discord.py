from flask_discord_interactions import Message, Embed, ActionRow, ButtonStyles, Button
from hub.models import User, Game, VoteType, LanGameProposal, LanGameProposalVote
from flask_discord_interactions.models.embed import Media, Field
from app import app, db, discord_interactions
from sqlalchemy.exc import IntegrityError
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
    if g.lan_games_status == 'disabled':
        return Message(
            'On ne choisis pas encore les jeux pour la LAN !'
        )

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
def _handle_vote_button(ctx, game_id: int, vote_type: Literal['YES', 'NEUTRAL', 'NO']):
    user = db.session.get(User, ctx.author.id)

    if not user:
        message = 'Tu n\'a pas encore de compte sur notre intranet. Crée-le ici {} et rééssaye. Tu peux également voter ici {}.'.format(
            url_for('login', _external=True),
            url_for('lan_games_vote', _external=True),
        )
    elif not user.is_lan_participant:
        message = 'Désolé, tu ne fais pas partie des participants à la LAN.'
    else:
        if g.lan_games_status == 'disabled':
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


def send_proposal_message(user: User, game: Game) -> Response:
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

    return _send_message(app.config['DISCORD_LAN_CHANNEL_ID'], data, content_type)


def send_chicken_dinner_message(match_id: str, map_name: str, game_mode_name: str, participants: List[Dict]) -> Response:
    def _participant_name(participant: Dict) -> str:
        return '[{0}](https://pubg.sh/{0}/{1}/{2})'.format(
            participant['attributes']['stats']['name'],
            participant['attributes']['shardId'],
            match_id
        )

    last_participant = None
    participants_for_player_names = participants

    if len(participants) > 1:
        last_participant = participants[-1]
        participants_for_player_names = participants[:-1]

    participants_names = ', '.join([
        _participant_name(participant) for participant in participants_for_player_names
    ])

    if last_participant:
        participants_names += ' et ' + _participant_name(last_participant)

    pluralize = len(participants) > 1

    contents = [
        f'Les parents de {participants_names} peuvent enfin être fiers grâce à {"leur" if pluralize else "son"} top 1 en **{game_mode_name}** sur **{map_name}** !',
        f'On y croyait plus, un Chicken Dinner de plus pour {participants_names} en **{game_mode_name}** sur **{map_name}** !',
        f'C\'est sur **{map_name}** en **{game_mode_name}** que {participants_names} {"ont" if pluralize else "a"} brillé (pour une fois) par {"leur" if pluralize else "son"} Chicken Dinner !',
        f'Dieu existe et le prouve à travers {participants_names} et {"leur" if pluralize else "son"} top 1 en **{game_mode_name}** sur **{map_name}** !',
        f'{participants_names} {"dormiront" if pluralize else "dormira"} l\'esprit tranquille ce soir grâce à {"leur" if pluralize else "son"} top 1 en **{game_mode_name}** sur **{map_name}** !',
        f'C\'est {participants_names} qui {"régalent" if pluralize else "régale"} ce soir avec {"leur" if pluralize else "son"} Chicken Dinner en **{game_mode_name}** sur **{map_name}** !',
        f'La zone est pacifiée sur **{map_name}** en **{game_mode_name}** grâce au top 1 de {participants_names} !',
        f'C\'était mal barré comme d\'habitude sur **{map_name}** en **{game_mode_name}**, mais le skill (plus probablement la chance) a fait que {participants_names} {"finissent" if pluralize else "finisse"} top 1 !',
        f'Vous ne devinerez jamais comment ce top 1 hallucinant a été atteint par {participants_names} en **{game_mode_name}** sur **{map_name}** !',
    ]

    participants_names_list = [
        participant['attributes']['stats']['name'] for participant in participants
    ]

    if 'Pepsite' in participants_names_list:
        contents.append(
            f'{participants_names} {"ont" if pluralize else "a"} atteint le top 1 sur **{map_name}** en **{game_mode_name}**, heureusement que (pour une fois) la conduite de Pepsite ne l\'a pas empêché !'
        )

    if 'DrMastock' in participants_names_list:
        contents.append(
            f'Chicken Dinner pour {participants_names}, sûrement grâce à la x8 de DrMastock trouvée au dernier moment sur **{map_name}** en **{game_mode_name}** !'
        )

    images = [
        'https://pbs.twimg.com/media/EXfqIngWsAA6gBq.jpg',
        'https://i.imgur.com/M33pWNM.png',
        'https://c.tenor.com/vOKwPz3lifIAAAAC/tenor.gif',
        'https://media.toucharger.com/web/toucharger/upload/image_domain/7/5/75657/75657.gif',
        'https://c.tenor.com/z04usSAGgJwAAAAd/tenor.gif',
        'https://c.tenor.com/XYvg-iC6PT4AAAAC/tenor.gif',
        'https://c.tenor.com/fit861DxTeQAAAAC/tenor.gif',
        'https://c.tenor.com/6XA-L01v3RQAAAAC/tenor.gif',
    ]

    data, content_type = Message(
        '🐔 ' + secrets.choice(contents),
        embed=Embed(
            title='Stats',
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


def _vote_type_emoji(vote_type: VoteType) -> str:
    if vote_type == vote_type.YES:
        return '👍'

    if vote_type == vote_type.NEUTRAL:
        return '😐'

    if vote_type == vote_type.NO:
        return '👎'

    return ''
