from hub.pubg import PUBGApiClient, MATCH_TYPES_NAMES
from hub.discord import send_chicken_dinner_message
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects import postgresql
from typing import Dict, Optional
from app import app, db, cache
from hub.models import Game
from rich import print_json
import sqlalchemy as sa
from hub import igdb
import click

CHICKEN_DINNER_LOCK_CACHE_KEY = 'chicken_dinner_processing'
CHICKEN_DINNER_PROCESSED_CACHE_KEY = 'chicken_dinner_processed'
PUBG_SHARD = 'steam'


@app.cli.command()
def cc() -> None:
    """Supprime le cache."""
    click.echo('Suppression du cache')

    cache.clear()

    click.secho('Effectué', fg='green')


@app.cli.command()
@click.argument('resource')
@click.option('--fields')
@click.option('--exclude')
@click.option('--where')
@click.option('--limit', type=click.IntRange(1))
@click.option('--offset', type=click.IntRange(0))
@click.option('--sort')
@click.option('--search')
def query_igdb(
    resource: str,
    fields: Optional[str] = None,
    exclude: Optional[str] = None,
    where: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    sort: Optional[str] = None,
    search: Optional[str] = None
) -> None:
    """Envoie une requête à l'API IGDB et affiche le résultat."""
    client = igdb.IgdbApiClient(
        app.config['IGDB_API_CLIENT_ID'],
        app.config['IGDB_API_CLIENT_SECRET'],
        cache
    )

    try:
        print_json(
            data=client.call(resource, fields, exclude, where, limit, offset, sort, search)
        )
    except Exception as e:
        click.secho(e, fg='red')


@app.cli.command()
def update_games() -> None:
    """Met à jour la base de données interne des jeux depuis IGDB."""
    click.echo('Mise à jour des jeux depuis IGDB...')

    offset = 0
    limit = 500
    all_game_ids = set()

    client = igdb.IgdbApiClient(
        app.config['IGDB_API_CLIENT_ID'],
        app.config['IGDB_API_CLIENT_SECRET'],
        cache
    )

    def get_url(game: Dict) -> Optional[str]:
        if 'websites' not in game or not game['websites']:
            return None

        excluded = [
            igdb.Website.Discord,
            igdb.Website.Twitch,
        ]

        priorities = [
            igdb.Website.Steam,
            igdb.Website.Epic,
            igdb.Website.Gog,
            igdb.Website.Official,
            igdb.Website.Wiki,
        ]

        websites = {
            website['type']: website['url'] for website in game['websites'] if website['type'] not in excluded
        }

        for priority in priorities:
            url = websites.get(priority)

            if url:
                return url

        try:
            return websites.get(next(iter(websites)))
        except StopIteration:
            return None

    def get_image_id(game: Dict) -> Optional[str]:
        if 'cover' not in game or not game['cover']:
            return None

        return game['cover']['image_id']

    while True:
        click.echo(f'  Téléchargement du paquet {offset} - {offset + limit}...')

        raw_games = client.call(
            'games',
            fields='id, name, websites.type, websites.url, cover.image_id',
            where=f'game_type = ({igdb.GameType.MainGame}, {igdb.GameType.Mod}, {igdb.GameType.Remake}, {igdb.GameType.Remaster}) & (game_status = ({igdb.GameStatus.Released}, {igdb.GameStatus.Beta}, {igdb.GameStatus.EarlyAccess}) | game_status = null) & game_modes = ({igdb.GameMode.Multiplayer}, {igdb.GameMode.CoOperative}, {igdb.GameMode.SplitScreen}, {igdb.GameMode.Mmo}, {igdb.GameMode.BattleRoyale}) & platforms = ({igdb.Platform.Linux}, {igdb.Platform.Windows}, {igdb.Platform.OculusVr}, {igdb.Platform.SteamVr})',
            offset=offset,
            limit=limit,
        )

        if not raw_games:
            break

        games = [
            {
                'id': game['id'],
                'name': game['name'],
                'url': get_url(game),
                'image_id': get_image_id(game),
            } for game in raw_games
        ]

        query = postgresql.insert(Game).values(games)

        click.echo('  Mise à jour de la BDD...')

        all_game_ids.update([
            str(game['id']) for game in games
        ])

        db.session.execute(query.on_conflict_do_update(
            index_elements=[Game.id],
            set_={
                Game.name: query.excluded.name,
                Game.url: query.excluded.url,
                Game.image_id: query.excluded.image_id,
            }
        ))

        offset += limit

    click.echo('Suppression des anciens jeux...')

    db.session.execute(
        sa.text(f'DELETE FROM {Game.__tablename__} WHERE id NOT IN ({",".join(all_game_ids)});')
    )

    db.session.commit()

    click.secho('Effectué', fg='green')


@app.cli.command()
def chicken_dinner() -> None:
    """Envoie nos Chicken Dinner sur Discord."""
    if cache.get(CHICKEN_DINNER_LOCK_CACHE_KEY):
        raise click.Abort('Un traitement est déjà en cours')

    cache.set(CHICKEN_DINNER_LOCK_CACHE_KEY, True, 0)

    try:
        processed = cache.get(CHICKEN_DINNER_PROCESSED_CACHE_KEY) or {}

        client = PUBGApiClient(app.config['PUBG_API_JWT_TOKEN'], cache)

        click.echo('Récupération des joueurs...')

        players = client.get_players(PUBG_SHARD, player_names=app.config['PUBG_PLAYER_NAMES_INTERNAL'])['data']

        now = datetime.now(timezone.utc)
        cached_since = now - timedelta(days=20)

        click.echo('  {} joueurs récupérés'.format(len(players)))

        matches_id = set()

        for player in players:
            for match in player['relationships']['matches']['data']:
                matches_id.add(match['id'])

        click.echo('Récupération de {} matches...'.format(len(matches_id)))

        matches = [
            client.get_match(PUBG_SHARD, match_id) for match_id in matches_id
        ]

        if processed:
            matches = [
                match for match in matches if match['data']['id'] not in processed
            ]

            if matches:
                click.echo('{} nouveaux matches à traiter'.format(len(matches)))

                processed.update({
                    match['data']['id']: now for match in matches
                })

                player_names_to_match = app.config['PUBG_PLAYER_NAMES_INTERNAL'] + app.config['PUBG_PLAYER_NAMES_EXTERNAL']

                for match in matches:
                    click.echo('Traitement de {}'.format(match['data']['id']))

                    if match['data']['attributes']['matchType'] not in MATCH_TYPES_NAMES.keys():
                        click.secho('  Pas un match qui nous intéresse', fg='yellow')

                        continue

                    participants = [
                        participant for participant in match['included'] if participant['type'] == 'participant' and participant['attributes']['stats']['name'] in player_names_to_match
                    ]

                    participants.sort(key=lambda p: p['attributes']['stats']['kills'], reverse=True)

                    participants_ids = [
                        participant['id'] for participant in participants
                    ]

                    click.echo('  {} joueurs trouvés'.format(len(participants)))

                    rosters = sorted(
                        [
                            roster for roster in match['included'] if roster['type'] == 'roster'
                        ],
                        key=lambda roster: roster['attributes']['stats']['rank']
                    )

                    total_teams = len(rosters)
                    roster_participant_ids = []
                    participants_roster = None

                    for roster in rosters:
                        roster_participant_ids = [
                            roster_participant['id'] for roster_participant in roster['relationships']['participants']['data']
                        ]

                        if any(True for participant_id in participants_ids if participant_id in roster_participant_ids):
                            participants_roster = roster

                            break

                    if not participants_roster:
                        click.secho('  Equipe pas trouvée', fg='red')

                        continue

                    other_participant_ids = [
                        roster_participant_id for roster_participant_id in roster_participant_ids if roster_participant_id not in participants_ids
                    ]

                    other_participants_count = len(other_participant_ids)

                    participants_rank = participants_roster['attributes']['stats']['rank']

                    if participants_rank <= 3 or participants_rank == total_teams:
                        click.secho(f'  {participants_rank} sur {total_teams}', fg='green')
                    else:
                        click.secho('  Pas à envoyer', fg='yellow')

                        continue

                    send_chicken_dinner_message(
                        participants_rank,
                        total_teams,
                        match['data']['id'],
                        match['data']['attributes']['mapName'],
                        match['data']['attributes']['gameMode'],
                        match['data']['attributes']['matchType'],
                        match['data']['attributes']['duration'],
                        participants,
                        other_participants_count
                    )
            else:
                click.secho('Aucun nouveau match à envoyer', fg='yellow')

            processed = {
                mid: dt for mid, dt in processed.items() if dt >= cached_since
            }
        else:
            processed.update({
                match['data']['id']: now for match in matches
            })

            click.secho('1er traitement: aucune action à effectuer', fg='yellow')

        cache.set(
            CHICKEN_DINNER_PROCESSED_CACHE_KEY,
            processed,
            0
        )
    except Exception as e:
        app.logger.exception('Une erreur est survenue lors du traitement des Chicken Dinner')

        if not app.config['DEBUG'] and app.config['SENTRY_DSN']:
            import sentry_sdk

            sentry_sdk.capture_exception()
    finally:
        cache.set(CHICKEN_DINNER_LOCK_CACHE_KEY, False, 0)

    click.secho('Effectué', fg='green')


@app.cli.command()
def chicken_dinner_clear_lock() -> None:
    """Supprime le verrou du traitement des Chicken Dinner."""
    click.echo('Suppression du verrou...')

    cache.set(CHICKEN_DINNER_LOCK_CACHE_KEY, False, 0)

    click.secho('Effectué', fg='green')


@app.cli.command()
def chicken_dinner_clear_processed() -> None:
    """Supprime tous les matchs déjà traités."""
    click.echo('Suppression des matchs...')

    cache.set(CHICKEN_DINNER_PROCESSED_CACHE_KEY, {}, 0)

    click.secho('Effectué', fg='green')
