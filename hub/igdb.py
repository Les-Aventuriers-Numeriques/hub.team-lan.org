from ratelimit import limits, sleep_and_retry
from requests.exceptions import HTTPError
from typing import Dict, Optional
from flask_caching import Cache
import requests

requests = requests.Session()

API_BASE_URL = 'https://api.igdb.com/v4/'
OAUTH2_TOKEN_ENDPOINT = 'https://id.twitch.tv/oauth2/token'


class IgdbApiErrorResponse(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f'[{code}] {message}')


class IgdbApiClient:
    client_id: str
    client_secret: str

    def __init__(self, client_id: str, client_secret: str, cache: Cache) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache = cache

    def get_token(self) -> str:
        cache_key = f'igdb_api_client.token.{self.client_id}'

        token = self.cache.get(cache_key)

        if token:
            return token

        headers = {
            'Accept': 'application/json'
        }

        json = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }

        response = requests.post(OAUTH2_TOKEN_ENDPOINT, headers=headers, json=json)

        try:
            response.raise_for_status()
        except HTTPError as e:
            if 'application/json' in e.response.headers.get('Content-Type', ''):
                error = e.response.json()
                code = error['status']
                message = error['message']

                raise IgdbApiErrorResponse(code, message) from e
            else:
                raise

        json = response.json()

        self.cache.set(cache_key, json['access_token'], json['expires_in'] - 5)

        return json['access_token']

    @sleep_and_retry
    @limits(calls=4, period=1)
    def call(self, resource: str, query: Optional[str] = None) -> Dict:
        url = API_BASE_URL + resource

        headers = {
            'Accept': 'application/json',
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.get_token()}',
        }

        response = requests.post(url, headers=headers, data=query)

        try:
            response.raise_for_status()
        except HTTPError as e:
            if 'application/json' in e.response.headers.get('Content-Type', ''):
                error = e.response.json()

                if isinstance(error, list):
                    error = error[0]

                    code = error['status']
                    message = error['title']
                else:
                    code = 0
                    message = error['message']

                raise IgdbApiErrorResponse(code, message) from e
            else:
                raise

        return response.json()


__all__ = ['IgdbApiErrorResponse', 'IgdbApiClient']