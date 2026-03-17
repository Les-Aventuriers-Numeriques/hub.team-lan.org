from app import app, db, cache, discord_interactions
from sqlalchemy.dialects import postgresql
from typing import Dict, Optional
from hub.models import Game
from rich import print_json
import sqlalchemy as sa
from hub import igdb
import click


@app.cli.command()
def cc() -> None:
    """Supprime le cache."""
    click.echo('Suppression du cache')

    cache.clear()

    click.secho('Effectué', fg='green')


@app.cli.command()
def update_discord_commands() -> None:
    """Met à jour les commandes Discord."""
    click.echo('Mise à jour des commandes Discord...')

    discord_interactions.update_commands(guild_id=app.config['DISCORD_GUILD_ID'])

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
def games_for_main_site() -> None:
    """Génère la liste des jeux joués pour le site principal."""
    games = {
        'games_being_played': (
            147187, # Broken Arrow
            153807, # Call to Arms - Gates of Hell
            59078, # Door Kickers 2
            15894, # Hearts of Iron IV
            83368, # Mindustry
            18871, # Parkitect
            3277, # Rust
            359709, # RWR 2
            90558, # Satisfactory
            9495, # Squad
        ),
        'previously_played_games': (
            122809, # 10 Miles To Safety
            572, # Arma 2
            1881, # Arma 3
            55056, # Age of Empires II
            127910, # Blitzkrieg Mod
            17432, # Call to Arms
            654, # Company of Heroes
            1369, # Company of Heroes 2
            124954, # Crusader Kings III
            262186, # Delta Force
            3099, # Door Kickers
            32365, # Hell Let Loose
            2949, # Killing Floor
            6748, # Killing Floor 2
            358689, # LA Mod
            121, # Minecraft
            5572, # Men of War: Assault Squad 2
            1338, # Prison Architect
            27789, # PUBG
            79694, # Project Reality: Battlefield 2
            11198, # Rocket League
            11584, # RUNNING WITH RIFLES
            35073, # Thunder Tier One
            2165, # War Thunder
            20910, # World War Z
        )
    }

    for section_name, game_ids in games.items():
        click.echo(f'\'{section_name}\': [')

        games = db.session.execute(
            sa.select(Game).where(Game.id.in_(game_ids)).order_by(Game.name.asc())
        ).scalars().all()

        for game in games:
            click.echo(f'    (\'{game.name}\', \'{game.url}\', \'{game.image_url}\'),')

        click.echo('],')


@app.cli.command()
@click.option('--delete', is_flag=True)
def update_games(delete: bool = False) -> None:
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

    def get_single_owner_enough(game: Dict) -> bool:
        if 'multiplayer_modes' not in game or not game['multiplayer_modes']:
            return False

        multiplayer_modes = {
            multiplayer_mode.get('platform'): multiplayer_mode for multiplayer_mode in game['multiplayer_modes']
        }

        priorities = [
            None, # Oui.
            igdb.Platform.Windows,
            igdb.Platform.Linux,
            igdb.Platform.OculusVr,
            igdb.Platform.SteamVr,
        ]

        multiplayer_mode = None

        for priority in priorities:
            multiplayer_mode = multiplayer_modes.get(priority)

            if multiplayer_mode:
                break

        if not multiplayer_mode:
            return False

        offlinecoop = multiplayer_mode.get('offlinecoop', False)
        offlinecoopmax = multiplayer_mode.get('offlinecoopmax', 0)
        offlinemax = multiplayer_mode.get('offlinemax', 0)
        splitscreen = multiplayer_mode.get('splitscreen', False)

        return offlinecoop or offlinecoopmax > 0 or offlinemax > 0 or splitscreen

    forced_game_ids = ', '.join([
        str(game_id) for game_id in app.config['IGDB_API_FORCED_GAMES']
    ])

    game_types = ', '.join([
        str(game_type) for game_type in [
            igdb.GameType.MainGame,
            igdb.GameType.Mod,
            igdb.GameType.Remake,
            igdb.GameType.Remaster,
        ]
    ])

    game_statuses = ', '.join([
        str(game_status) for game_status in [
            igdb.GameStatus.Released,
            igdb.GameStatus.Beta,
            igdb.GameStatus.EarlyAccess,
        ]
    ])

    game_modes = ', '.join([
        str(game_mode) for game_mode in [
            igdb.GameMode.Multiplayer,
            igdb.GameMode.CoOperative,
            igdb.GameMode.SplitScreen,
            igdb.GameMode.Mmo,
            igdb.GameMode.BattleRoyale,
        ]
    ])

    platforms = ', '.join([
        str(platform) for platform in [
            igdb.Platform.Linux,
            igdb.Platform.Windows,
            igdb.Platform.OculusVr,
            igdb.Platform.SteamVr,
        ]
    ])

    while True:
        click.echo(f'  Téléchargement du paquet {offset} - {offset + limit}...')

        raw_games = client.call(
            'games',
            fields='id, name, websites.type, websites.url, cover.image_id, multiplayer_modes.*',
            where=f'id = ({forced_game_ids}) | (game_type = ({game_types}) & (game_status = ({game_statuses}) | game_status = null) & game_modes = ({game_modes}) & platforms = ({platforms}))',
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
                'single_owner_enough': get_single_owner_enough(game),
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
                Game.single_owner_enough: query.excluded.single_owner_enough,
            }
        ))

        offset += limit

    if delete:
        click.echo('Suppression des anciens jeux...')

        db.session.execute(
            sa.text(f'DELETE FROM {Game.__tablename__} WHERE id NOT IN ({",".join(all_game_ids)});')
        )

    db.session.commit()

    click.secho('Effectué', fg='green')
