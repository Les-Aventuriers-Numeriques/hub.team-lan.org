from sqlalchemy.dialects import postgresql
from os import makedirs, path
from hub.models import Game
from app import app, db
import requests
import click
import csv


@app.cli.command()
def update_games() -> None:
    """Met à jour la base de données interne des jeux Steam."""
    click.echo('Téléchargement de la liste des jeux Steam...')

    local_csv = 'data/games.csv'
    remote_csv = 'https://huggingface.co/datasets/FronkonGames/steam-games-dataset/resolve/main/games.csv'

    makedirs(path.dirname(local_csv), exist_ok=True)

    with requests.get(remote_csv, stream=True) as response:
        response.raise_for_status()

        with open(local_csv, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

    click.echo('Mise à jour des jeux Steam...')

    with open(local_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        games = [
            {
                'id': game['AppID'],
                'name': game['Name'],
            } for game in reader
        ]

    ins = postgresql.insert(Game).values(games)

    db.session.execute(ins.on_conflict_do_nothing())
    db.session.commit()

    click.secho('Effectué', fg='green')
