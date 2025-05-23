from hub.pubg import PUBGApiClient, MATCH_TYPES_NAMES
from hub.discord import send_chicken_dinner_message
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects import postgresql
from app import app, db, cache
from hub.models import Game
import sqlalchemy as sa
import requests
import click
import csv

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
def update_games() -> None:
    """Met à jour la base de données interne des jeux Steam."""
    click.echo('Mise à jour des jeux Steam...')

    have_more_results = True
    last_appid = None
    all_app_ids = set()

    while have_more_results:
        click.echo('  Téléchargement du paquet...')

        response = requests.get(
            'https://api.steampowered.com/IStoreService/GetAppList/v1/',
            params={
                'key': app.config['STEAM_API_KEY'],
                'include_games': 'true',
                'include_dlc': 'false',
                'include_software': 'false',
                'include_videos': 'false',
                'include_hardware': 'false',
                'max_results': 5000,
                'last_appid': last_appid,
            },
            headers={
                'Accept': 'application/json'
            }
        )

        response.raise_for_status()

        json = response.json()['response']

        games = [
            {
                'id': game['appid'],
                'name': game['name'],
            } for game in json['apps'] if game['name']
        ]

        have_more_results = json.get('have_more_results', False)
        last_appid = json.get('last_appid')

        query = postgresql.insert(Game).values(games)

        click.echo('  Mise à jour de la BDD...')

        all_app_ids.update([
            str(game['id']) for game in games
        ])

        db.session.execute(query.on_conflict_do_update(
            index_elements=[Game.id],
            set_={
                Game.name: query.excluded.name,
            }
        ))

    click.echo('Mise à jour des jeux personnalisés...')

    with open('storage/data/games.csv', 'r', encoding='utf-8') as f:
        i = -1
        games = []

        for row in csv.DictReader(f):
            games.append({
                'id': i,
                'name': row['name'],
                'custom_url': row['url'],
            })

            i -= 1

    all_app_ids.update([
        str(game['id']) for game in games
    ])

    query = postgresql.insert(Game).values(games)

    click.echo('  Mise à jour de la BDD...')

    db.session.execute(query.on_conflict_do_update(
        index_elements=[Game.id],
        set_={
            Game.name: query.excluded.name,
            Game.custom_url: query.excluded.custom_url,
        }
    ))

    db.session.commit()

    click.echo('Suppression des anciens jeux...')

    db.session.execute(
        sa.text(f'DELETE FROM {Game.__tablename__} WHERE id NOT IN ({",".join(all_app_ids)});')
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
@click.argument('dt')
def chicken_dinner_clear_processed() -> None:
    """Supprime tous les matchs déjà traités."""
    click.echo('Suppression des matchs...')

    cache.set(CHICKEN_DINNER_PROCESSED_CACHE_KEY, {}, 0)

    click.secho('Effectué', fg='green')
