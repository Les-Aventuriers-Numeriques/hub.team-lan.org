from sqlalchemy.dialects import postgresql
from hub.models import Game
from app import app, db
import requests
import click


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

        db.session.execute(query.on_conflict_do_nothing())

    db.session.commit()

    click.secho('Effectué', fg='green')
