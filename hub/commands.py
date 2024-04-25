from sqlalchemy.dialects.postgresql import insert
from hub.models import Game
from app import app, db
import requests
import click


@app.cli.command()
def update_steam_apps() -> None:
    """Met à jour la base de données des apps publiques Steam."""
    click.echo('Mise à jour des apps publiques Steam...')

    response = requests.get('https://api.steampowered.com/ISteamApps/GetAppList/v2/')
    response.raise_for_status()

    games = [
        {
            'steam_appid': app['appid'],
            'name': app['name'],
        } for app in response.json()['applist']['apps'] if app['name']
    ]

    ins = insert(Game).values(games)
    ins.on_conflict_do_nothing()

    db.session.execute(ins)
    db.session.commit()

    click.secho('Effectué', fg='green')
