import sys
from logging import getLogger
from typing import Union, List, Tuple

from aiohttp import ClientSession, ContentTypeError

from a01.auth import AuthSettings
from a01.common import A01Config


class AsyncSession(ClientSession):
    def __init__(self) -> None:
        super(AsyncSession, self).__init__()
        self.auth = AuthSettings()
        self.endpoint = A01Config().ensure_config().endpoint_uri
        self.logger = getLogger(__name__)

    def get_path(self, path: str) -> str:
        return f'{self.endpoint}/{path}'

    def get_headers(self) -> dict:
        if self.auth.is_expired and not self.auth.refresh():
            self.logger.error('Fail to refresh access token. Please login again.')
            sys.exit(1)

        return {'Authorization': self.auth.access_token}

    async def post_auth(self, path: str) -> Tuple[int, str]:
        async with self.post(self.get_path(path), headers=self.get_headers()) as resp:
            content = await resp.text()
            return resp.status, content

    async def delete_auth(self, path: str) -> Tuple[int, str]:
        async with self.delete(self.get_path(path), headers=self.get_headers()) as resp:
            content = await resp.text()
            return resp.status, content

    async def get_json(self, path: str) -> Union[List, dict, float, str, None]:
        async with self.get(self.get_path(path), headers=self.get_headers()) as resp:
            try:
                return await resp.json()
            except ContentTypeError:
                self.logger.error('Incorrect content type')
                self.logger.error(await resp.text())
                raise
