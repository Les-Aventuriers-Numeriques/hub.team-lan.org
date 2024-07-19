from sqlalchemy.dialects import postgresql
from datetime import datetime, timezone
from hub.pubg import PUBGApiClient
from app import app, db, cache
from hub.models import Game
import requests
import click
import csv


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
    lock_cache_key = 'chicken_dinner_processing'
    last_processed_cache_key = 'chicken_dinner_last_processed'
    pubg_shard = 'steam'

    if cache.get(lock_cache_key):
        click.secho('Un traitement est déjà en cours', fg='yellow')

        return

    cache.set(lock_cache_key, True)
    last_processed = cache.get(last_processed_cache_key)

    client = PUBGApiClient(app.config['PUBG_API_JWT_TOKEN'], cache)

    click.secho('Récupération des joueurs...')

    players = client.get_players(pubg_shard, player_names=app.config['PUBG_PLAYER_NAMES_INTERNAL'])['data']

    click.secho('  {} joueurs récupérés'.format(len(players)))

    matches_id = set()

    for player in players:
        for match in player['relationships']['matches']['data']:
            matches_id.add(match['id'])

    click.secho('Récupération de {} matches...'.format(len(matches_id)))

    matches = {
        match_id: client.get_match(pubg_shard, match_id) for match_id in matches_id
    }

    if last_processed:
        matches = {
            match_id: match for match_id, match in matches.items() if datetime.fromisoformat(match['attributes']['createdAt']) >= last_processed
        }

        if matches:
            click.secho('  {} nouveaux matches à envoyer'.format(len(matches)))
        else:
            click.secho('  Aucun nouveau match à envoyer', fg='yellow')
    else:
        click.secho('1er traitement: aucune action à effectuer', fg='yellow')

    cache.set(last_processed_cache_key, datetime.now(timezone.utc))
    cache.set(lock_cache_key, False)

    click.secho('Effectué', fg='green')
