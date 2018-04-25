from typing import List

import asyncio
import aiohttp

from a01.auth import AuthSettings
from a01.common import A01Config
from a01.models import Task


async def query_tasks_async(ids: List[str]) -> List[Task]:
    results = []
    endpoint = A01Config().ensure_config().endpoint_uri
    async with aiohttp.ClientSession(headers={'Authorization': AuthSettings().access_token}) as session:
        for task_id in ids:
            async with session.get(f'{endpoint}/task/{task_id}') as resp:
                json_body = await resp.json()
                results.append(Task.from_dict(json_body))

    return results


async def query_tasks_by_run_async(run_id: str) -> List[Task]:
    endpoint = A01Config().ensure_config().endpoint_uri
    async with aiohttp.ClientSession(headers={'Authorization': AuthSettings().access_token}) as session:
        async with session.get(f'{endpoint}/run/{run_id}/tasks') as resp:
            json_body = await resp.json()
            return [Task.from_dict(data) for data in json_body]


def query_tasks(ids: List[str]) -> List[Task]:
    return asyncio.get_event_loop().run_until_complete(query_tasks_async(ids))


def query_tasks_by_run(run_id: str) -> List[Task]:
    return asyncio.get_event_loop().run_until_complete(query_tasks_by_run_async(run_id))
