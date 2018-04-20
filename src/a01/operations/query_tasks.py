from typing import List

import asyncio
import aiohttp

from a01.common import A01Config
from a01.models import Task
from a01.auth import AuthSettings


async def query_tasks_async(ids: List[str]) -> List[Task]:
    endpoint = A01Config().ensure_config().endpoint_uri
    access_token = AuthSettings().access_token
    headers = {'Authorization': access_token}

    results = []
    async with aiohttp.ClientSession(headers=headers) as session:
        for task_id in ids:
            async with session.get(f'{endpoint}/task/{task_id}') as resp:
                json_body = await resp.json()
                results.append(Task.from_dict(json_body))

    return results


def query_tasks(ids: List[str]) -> List[Task]:
    loop = asyncio.get_event_loop()
    tasks = loop.run_until_complete(query_tasks_async(ids))

    return tasks
