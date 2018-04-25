from urllib.parse import urlencode

import asyncio
import aiohttp

from a01.auth import AuthSettings
from a01.common import A01Config
from a01.models import Run, RunsView


async def query_run_async(run_id: str) -> Run:
    endpoint = A01Config().ensure_config().endpoint_uri
    async with aiohttp.ClientSession(headers={'Authorization': AuthSettings().access_token}) as session:
        async with session.get(f'{endpoint}/run/{run_id}') as resp:
            json_body = await resp.json()
            return Run.from_dict(json_body)


async def query_runs_async(**kwargs) -> RunsView:
    endpoint = A01Config().ensure_config().endpoint_uri
    async with aiohttp.ClientSession(headers={'Authorization': AuthSettings().access_token}) as session:
        url = f'{endpoint}/runs'
        query = {}
        for key, value in kwargs.items():
            if value is not None:
                query[key] = value

        if query:
            url = f'{url}?{urlencode(query)}'

        async with session.get(url) as resp:
            json_body = await resp.json()
            return RunsView(runs=[Run.from_dict(each) for each in json_body])


def query_run(run_id: str) -> Run:
    return asyncio.get_event_loop().run_until_complete(query_run_async(run_id))


def query_runs(owner: str = None, last: int = 10, skip: int = 0) -> RunsView:
    return asyncio.get_event_loop().run_until_complete(query_runs_async(owner=owner, last=last, skip=skip))
