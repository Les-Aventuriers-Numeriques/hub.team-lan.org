from hub.discord import send_chicken_dinner_message
from sqlalchemy.dialects import postgresql
from datetime import datetime, timezone
from hub.pubg import PUBGApiClient
from app import app, db, cache
from hub.models import Game
import requests
import click
import csv

CHICKEN_DINNER_LOCK_CACHE_KEY = 'chicken_dinner_processing'
CHICKEN_DINNER_LAST_PROCESSED_CACHE_KEY = 'chicken_dinner_last_processed'
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

    click.secho('Effectué', fg='green')


@app.cli.command()
def chicken_dinner() -> None:
    """Envoie nos Chicken Dinners sur Discord."""
    if cache.get(CHICKEN_DINNER_LOCK_CACHE_KEY):
        click.secho('Un traitement est déjà en cours', fg='yellow')

        return

    cache.set(CHICKEN_DINNER_LOCK_CACHE_KEY, True, 0)

    try:
        last_processed = cache.get(CHICKEN_DINNER_LAST_PROCESSED_CACHE_KEY)

        client = PUBGApiClient(app.config['PUBG_API_JWT_TOKEN'], cache)

        click.echo('Récupération des joueurs...')

        players = client.get_players(PUBG_SHARD, player_names=app.config['PUBG_PLAYER_NAMES_INTERNAL'])['data']

        click.echo('  {} joueurs récupérés'.format(len(players)))

        matches_id = set()

        for player in players:
            for match in player['relationships']['matches']['data']:
                matches_id.add(match['id'])

        click.echo('Récupération de {} matches...'.format(len(matches_id)))

        matches = [
            client.get_match(PUBG_SHARD, match_id) for match_id in matches_id
        ]

        if last_processed:
            # matches = [
            #     match for match in matches if datetime.fromisoformat(match['data']['attributes']['createdAt']) >= last_processed
            # ]

            if matches:
                click.echo('{} nouveaux matches à traiter'.format(len(matches)))

                player_names_to_match = app.config['PUBG_PLAYER_NAMES_INTERNAL'] + app.config['PUBG_PLAYER_NAMES_EXTERNAL']

                for match in matches:
                    click.echo('Traitement de {}'.format(match['data']['id']))

                    participants = [
                        participant for participant in match['included'] if participant['type'] == 'participant' and participant['attributes']['stats']['name'] in player_names_to_match
                    ]

                    participants_ids = [
                        participant['id'] for participant in participants
                    ]

                    click.echo('  {} joueurs trouvés'.format(len(participants)))

                    winning_team = next(
                        (roster for roster in match['included'] if roster['type'] == 'roster' and roster['attributes']['won'] == 'true'),
                        None
                    )

                    winning_team_participants_ids = [
                        participant['id'] for participant in winning_team['relationships']['participants']['data']
                    ]

                    if not any(True for participant_id in participants_ids if participant_id in winning_team_participants_ids):
                        click.secho('  Pas un Chicken Dinner', fg='yellow')

                        continue

                    map_id = match['data']['attributes']['mapName']
                    map_name = map_id
                    game_mode_id = match['data']['attributes']['gameMode']
                    game_mode_name = game_mode_id

                    send_chicken_dinner_message(map_name, game_mode_name, participants)
            else:
                click.secho('Aucun nouveau match à envoyer', fg='yellow')
        else:
            click.secho('1er traitement: aucune action à effectuer', fg='yellow')

        cache.set(CHICKEN_DINNER_LAST_PROCESSED_CACHE_KEY, datetime.now(timezone.utc), 0)
    finally:
        cache.set(CHICKEN_DINNER_LOCK_CACHE_KEY, False, 0)

    click.secho('Effectué', fg='green')


@app.cli.command()
def chicken_dinner_clear_lock() -> None:
    """Supprime le verrou du traitement des Chicken Dinners."""
    click.echo('Suppression du verrou...')

    cache.set(CHICKEN_DINNER_LOCK_CACHE_KEY, False, 0)

    click.secho('Effectué', fg='green')
