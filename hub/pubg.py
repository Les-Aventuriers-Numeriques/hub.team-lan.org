from requests.exceptions import HTTPError
from typing import Dict, Optional, List
from flask_caching import Cache
from requests import Request
import requests

requests = requests.Session()

API_BASE_URL = 'https://api.pubg.com/'


class PUBGApiErrorResponse(Exception):
    errors: List[str]

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors

        super().__init__('; '.join(self.errors))


MAP_NAMES = {
    'Baltic_Main': 'Erangel',
    'Chimera_Main': 'Paramo',
    'Desert_Main': 'Miramar',
    'DihorOtok_Main': 'Vikendi',
    'Erangel_Main': 'Erangel',
    'Heaven_Main': 'Haven',
    'Kiki_Main': 'Deston',
    'Range_Main': 'Camp Jackal',
    'Savage_Main': 'Sanhok',
    'Summerland_Main': 'Karakin',
    'Tiger_Main': 'Taego',
    'Neon_Main': 'Rondo'
}

GAME_MODES = {
    'duo': 'Duo TPP',
    'duo-fpp': 'Duo FPP',
    'solo': 'Solo TPP',
    'solo-fpp': 'Solo FPP',
    'squad': 'Squad TPP',
    'squad-fpp': 'Squad FPP',
    'conquest-duo': 'Conquest Duo TPP',
    'conquest-duo-fpp': 'Conquest Duo FPP',
    'conquest-solo': 'Conquest Solo TPP',
    'conquest-solo-fpp': 'Conquest Solo FPP',
    'conquest-squad': 'Conquest Squad TPP',
    'conquest-squad-fpp': 'Conquest Squad FPP',
    'esports-duo': 'Esports Duo TPP',
    'esports-duo-fpp': 'Esports Duo FPP',
    'esports-solo': 'Esports Solo TPP',
    'esports-solo-fpp': 'Esports Solo FPP',
    'esports-squad': 'Esports Squad TPP',
    'esports-squad-fpp': 'Esports Squad FPP',
    'normal-duo': 'Duo TPP',
    'normal-duo-fpp': 'Duo FPP',
    'normal-solo': 'Solo TPP',
    'normal-solo-fpp': 'Solo FPP',
    'normal-squad': 'Squad TPP',
    'normal-squad-fpp': 'Squad FPP',
    'war-duo': 'War Duo TPP',
    'war-duo-fpp': 'War Duo FPP',
    'war-solo': 'War Solo TPP',
    'war-solo-fpp': 'War Solo FPP',
    'war-squad': 'Squad TPP',
    'war-squad-fpp': 'War Squad FPP',
    'zombie-duo': 'Zombie Duo TPP',
    'zombie-duo-fpp': 'Zombie Duo FPP',
    'zombie-solo': 'Zombie Solo TPP',
    'zombie-solo-fpp': 'Zombie Solo FPP',
    'zombie-squad': 'Zombie Squad TPP',
    'zombie-squad-fpp': 'Zombie Squad FPP',
    'lab-tpp': 'Lab TPP',
    'lab-fpp': 'Lab FPP',
    'tdm': 'Team Deathmatch'
}


class PUBGApiClient:
    jwt_token: str
    cache: Cache

    def __init__(self, jwt_token: str, cache: Cache) -> None:
        self.jwt_token = jwt_token
        self.cache = cache

    def get_players(self, shard: str, player_names: List[str] = None, player_ids: List[str] = None) -> Dict:
        if (not player_names and not player_ids) or (player_names and player_ids):
            raise ValueError('Either player_names or player_ids must be provided')

        filter_name = 'filter[{}]'.format(
            'playerNames' if player_names else 'playerIds'
        )

        filter_value = ','.join(player_names or player_ids)

        return self.call(
            f'shards/{shard}/players',
            {
                filter_name: filter_value
            }
        )

    def get_match(self, shard: str, match_id: str) -> Dict:
        return self.call(
            f'shards/{shard}/matches/{match_id}',
            needs_auth=False,
            cache_timeout=60 * 60 * 24 * 14 # 14 jours
        )

    def call(self, resource: str, params: Optional[Dict] = None, needs_auth: bool = True, cache_timeout: Optional[int] = None) -> Dict:
        url = API_BASE_URL + resource
        headers = {
            'Accept': 'application/vnd.api+json',
            'Accept-Encoding': 'gzip',
        }

        if self.jwt_token:
            headers.update({
                'Authorization': f'Bearer {self.jwt_token}'
            })
        elif needs_auth:
            raise ValueError(f'{resource} requires authentication but no JWT token has been set')

        request = requests.prepare_request(
            Request('GET', url, headers=headers, params=params)
        )

        cache_key = f'pubg_api_client.{request.method}.{request.url}'

        if self.cache and cache_timeout:
            response_data = self.cache.get(cache_key)

            if response_data:
                return response_data

        response = requests.send(request)

        try:
            response.raise_for_status()
        except HTTPError as e:
            if 'application/vnd.api+json' in e.response.headers.get('Content-Type', ''):
                errors = [
                    e['detail'] for e in e.response.json()['errors']
                ]

                raise PUBGApiErrorResponse(errors) from e
            else:
                raise

        response_data = response.json()

        if self.cache and cache_timeout and 200 <= response.status_code <= 299:
            self.cache.set(cache_key, response_data, cache_timeout)

        return response_data
