from typing import List

import asyncio

from a01.models import Task
from a01.transport import AsyncSession


async def query_tasks_async(ids: List[str]) -> List[Task]:
    results = []
    async with AsyncSession() as session:
        for task_id in ids:
            results.append(Task.from_dict(await session.get_json(f'task/{task_id}')))

    return results


async def query_tasks_by_run_async(run_id: str) -> List[Task]:
    async with AsyncSession() as session:
        return [Task.from_dict(each) for each in await session.get_json(f'run/{run_id}/tasks')]


def query_tasks(ids: List[str]) -> List[Task]:
    return asyncio.get_event_loop().run_until_complete(query_tasks_async(ids))


def query_tasks_by_run(run_id: str) -> List[Task]:
    return asyncio.get_event_loop().run_until_complete(query_tasks_by_run_async(run_id))
