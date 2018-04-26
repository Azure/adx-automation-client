from urllib.parse import urlencode

import asyncio

from a01.models import Run, RunsView
from a01.transport import AsyncSession


async def query_run_async(run_id: str) -> Run:
    async with AsyncSession() as session:
        return Run.from_dict(await session.get_json(f'run/{run_id}'))


async def query_runs_async(**kwargs) -> RunsView:
    async with AsyncSession() as session:
        url = 'runs'
        query = {}
        for key, value in kwargs.items():
            if value is not None:
                query[key] = value

        if query:
            url = f'{url}?{urlencode(query)}'

        json_body = await session.get_json(url)
        return RunsView(runs=[Run.from_dict(each) for each in json_body])


def query_run(run_id: str) -> Run:
    return asyncio.get_event_loop().run_until_complete(query_run_async(run_id))


def query_runs(owner: str = None, last: int = 10, skip: int = 0) -> RunsView:
    return asyncio.get_event_loop().run_until_complete(query_runs_async(owner=owner, last=last, skip=skip))
