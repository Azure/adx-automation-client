import sys
import logging
import json
from itertools import zip_longest

import colorama

from a01.cli import cmd, arg
from a01.output import output_in_table
from a01.models import TaskCollection, Task, Run
from a01.operations import download_recording_async, get_log_content_async
from a01.transport import AsyncSession


@cmd('get run', desc='Retrieve test run result')
@arg('run_id', help='The run id.', positional=True)
@arg('log', help="Include the failed tasks' logs.", option=('-l', '--log'))
@arg('recording', option=('-r', '--recording'),
     help='Download the recording files in recording directory at current working directory. The recordings '
          'are flatten with the full test path as the file name if --az-mode is not specified. If --az-mode is '
          'set, the recording files are arranged in directory structure mimic Azure CLI source code.')
@arg('show_all', option=['--show-all'], help='Show all the tasks results.')
@arg('recording_az_mode', option=['--az-mode'],
     help='When download the recording files the files are arranged in directory structure mimic Azure CLI '
          'source code.')
@arg('raw', help='For debug.')
async def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False,
                  show_all: bool = False, raw: bool = False) -> None:
    logger = logging.getLogger(__name__)

    try:
        async with AsyncSession() as session:
            tasks = [Task.from_dict(each) for each in await session.get_json(f'run/{run_id}/tasks')]
            tasks = TaskCollection(tasks, run_id)

            output_in_table(tasks.get_table_view(failed=not show_all), headers=tasks.get_table_header())
            output_in_table(tasks.get_summary(), tablefmt='plain')

            if log:
                for failure in tasks.get_failed_tasks():
                    output_in_table(zip_longest(failure.get_table_header(), failure.get_table_view()), tablefmt='plain')
                    output_in_table(await get_log_content_async(failure.log_resource_uri, session),
                                    tablefmt='plain',
                                    foreground_color=colorama.Fore.CYAN)
                output_in_table(tasks.get_summary(), tablefmt='plain')

            if recording:
                print()
                print('Download recordings ...')
                for task in tasks.tasks:
                    await download_recording_async(task.record_resource_uri,
                                                   task.identifier,
                                                   recording_az_mode,
                                                   session)

            if raw:
                run = Run.from_dict(await session.get_json(f'run/{run_id}'))
                print(json.dumps(run.to_dict(), indent=2))
    except ValueError as err:
        logger.error(err)
        sys.exit(1)
