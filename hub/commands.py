from app import app
import requests
import click


@app.cli.command()
def update_steam_apps() -> None:
    """Met à jour la base de données des apps publiques Steam."""
    click.echo('Mise à jour des apps publiques Steam...')

    response = requests.get('https://api.steampowered.com/ISteamApps/GetAppList/v2/')
    response.raise_for_status()

    apps = response.json()['applist']['apps']

    for app in apps:
        if not app['name']:
            continue

        print(app['name'])

    click.secho('Effectué', fg='green')
