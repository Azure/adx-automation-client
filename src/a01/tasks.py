from itertools import zip_longest

import colorama

import a01.cli
import a01.models
from a01.output import output_in_table


@a01.cli.cmd('get task', desc='Retrieve tasks information.')
@a01.cli.arg('ids', help='The task id. Support multiple IDs.', positional=True)
@a01.cli.arg('log', help='Retrieve the log of the task.', option=('-l', '--log'))
@a01.cli.arg('recording', option=('-r', '--recording'),
             help='Download the recording files in recording directory at current working directory. The recordings '
                  'are flatten with the full test path as the file name if --az-mode is not specified. If --az-mode is '
                  'set, the recording files are arranged in directory structure mimic Azure CLI source code.')
@a01.cli.arg('recording_az_mode', option=['--az-mode'],
             help='When download the recording files the files are arranged in directory structure mimic Azure CLI '
                  'source code.')
def get_task(ids: [str], log: bool = False, recording: bool = False, recording_az_mode: bool = False) -> None:
    for task_id in ids:
        task = a01.models.Task.get(task_id=task_id)
        output_in_table(zip_longest(task.get_table_header(), task.get_table_view()), tablefmt='plain')

        if log:
            print()
            output_in_table(task.get_log_content(), tablefmt='plain', foreground_color=colorama.Fore.CYAN)

        if recording:
            print()
            task.download_recording(recording_az_mode)

        print()
