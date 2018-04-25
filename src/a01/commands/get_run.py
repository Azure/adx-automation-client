import sys
import logging
import json
from itertools import zip_longest

import colorama

from a01.cli import cmd, arg
from a01.output import output_in_table
from a01.models import TaskCollection
from a01.operations import query_tasks_by_run, query_run


@cmd('get run', desc='Retrieve a run')
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
def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False,
            show_all: bool = False, raw: bool = False) -> None:
    logger = logging.getLogger(__name__)

    try:
        tasks = TaskCollection(query_tasks_by_run(run_id), run_id)
        output_in_table(tasks.get_table_view(failed=not show_all), headers=tasks.get_table_header())
        output_in_table(tasks.get_summary(), tablefmt='plain')

        if log:
            for failure in tasks.get_failed_tasks():
                output_in_table(zip_longest(failure.get_table_header(), failure.get_table_view()), tablefmt='plain')
                output_in_table(failure.get_log_content(), tablefmt='plain', foreground_color=colorama.Fore.CYAN)

            output_in_table(tasks.get_summary(), tablefmt='plain')

        if recording:
            print()
            print('Download recordings ...')
            for task in tasks.tasks:
                task.download_recording(recording_az_mode)

        if raw:
            run = query_run(run_id=run_id)
            print(json.dumps(run.to_dict(), indent=2))
    except ValueError as err:
        logger.error(err)
        sys.exit(1)
