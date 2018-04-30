import asyncio
import os
from typing import List, Tuple

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


async def download_recording_async(recording_uri: str,
                                   task_identifier: str,
                                   az_mode: bool,
                                   session: AsyncSession) -> None:
    if not recording_uri:
        return

    async with session.get(recording_uri) as resp:
        if resp.status != 200:
            return
        content = await resp.read()

    path_paths = task_identifier.split('.')
    if az_mode:
        module_name = path_paths[3]
        method_name = path_paths[-1]
        profile_name = path_paths[-4]
        recording_path = os.path.join('recording', f'azure-cli-{module_name}', 'azure', 'cli', 'command_modules',
                                      module_name, 'tests', profile_name, 'recordings', f'{method_name}.yaml')
    else:
        path_paths[-1] = path_paths[-1] + '.yaml'
        path_paths.insert(0, 'recording')
        recording_path = os.path.join(*path_paths)

    os.makedirs(os.path.dirname(recording_path), exist_ok=True)
    with open(recording_path, 'wb') as recording_file:
        recording_file.write(content)


async def get_log_content_async(log_uri: str, session: AsyncSession) -> List[Tuple[str, str]]:
    if not log_uri:
        return []
    async with session.get(log_uri) as resp:
        if resp.status == 404:
            return [('>', 'Log not found (task might still be running, or storage was not setup for this run)\n')]
        content = await resp.read()

    results = []
    for index, line in enumerate(content.decode('utf-8').split('\n')):
        results.append(('>', f' {index}\t{line}'))
    return results


def query_tasks(ids: List[str]) -> List[Task]:
    return asyncio.get_event_loop().run_until_complete(query_tasks_async(ids))


def query_tasks_by_run(run_id: str) -> List[Task]:
    return asyncio.get_event_loop().run_until_complete(query_tasks_by_run_async(run_id))
