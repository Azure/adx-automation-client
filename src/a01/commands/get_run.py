import sys
import logging
import re

from a01.cli import cmd, arg
from a01.output import (SequentialOutput, TaskBriefOutput, TaskLogOutput, JsonOutput, CommandOutput,
                        TasksSummary, TasksOutput)
from a01.models import Task, Run
from a01.operations import download_recording_async, get_log_content_async
from a01.transport import AsyncSession


@cmd('get run', desc='Retrieve test run result')
@arg('run_id', help='The run id.', positional=True)
@arg('log', help="Include the failed tasks' logs.", option=('-l', '--log'))
@arg('recording', option=('-r', '--recording'),
     help='Download the recording files in recording directory at current working directory. The recordings '
          'are flatten with the full test path as the file name if --az-mode is not specified. If --az-mode is '
          'set, the recording files are arranged in directory structure mimic Azure CLI source code.')
@arg('include_success', option=['--include-success'], help='Include results of the succeed tasks.')
@arg('recording_az_mode', option=['--az-mode'],
     help='When download the recording files the files are arranged in directory structure mimic Azure CLI '
          'source code.')
@arg('query', help='Filter the tasks\'s identifiers. It is a regex.')
@arg('raw', help='For debug.')
async def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False,
                  include_success: bool = False, query: str = None, raw: bool = False) -> CommandOutput:
    logger = logging.getLogger(__name__)
    output = SequentialOutput()

    try:
        async with AsyncSession() as session:
            tasks = [Task.from_dict(each) for each in await session.get_json(f'run/{run_id}/tasks')]
            if query:
                regex = re.compile(query)
                tasks = [each for each in tasks if regex.match(each.identifier)]
            tasks = sorted(tasks, key=lambda t: t.identifier)

            tasks_output = TasksOutput(tasks, include_success)

            output.append(tasks_output)
            output.append(TasksSummary(tasks))

            if log:
                for failure in tasks_output.get_failed_tasks():
                    output.append(TaskBriefOutput(failure))
                    output.append(TaskLogOutput(await get_log_content_async(failure.log_resource_uri, session)))
                output.append(TasksSummary(tasks))

            if raw:
                run = Run.from_dict(await session.get_json(f'run/{run_id}'))
                output.append(JsonOutput(run.to_dict()))

            if recording:
                for task in tasks:
                    await download_recording_async(task.record_resource_uri,
                                                   task.identifier,
                                                   recording_az_mode,
                                                   session)

            return output
    except ValueError as err:
        logger.error(err)
        sys.exit(1)
