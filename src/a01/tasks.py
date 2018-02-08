import json

import a01.cli
from a01.common import LOG_FILE, download_recording, A01Config
from a01.communication import session
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
@a01.cli.arg('details', option=('-d', '--details'),
             help='Show the details of the task.')
def get_task(ids: [str], log: bool = False, recording: bool = False, recording_az_mode: bool = False,
             details: bool = False) -> None:
    config = A01Config()
    config.ensure_config()

    for task_id in ids:
        resp = session.get(f'{config.endpoint_uri}/task/{task_id}')
        resp.raise_for_status()
        task = resp.json()
        view = [
            ('id', task['id']),
            ('result', task['result']),
            ('test', task['settings']['path']),
            ('duration(ms)', task['result_details']['duration'])
        ]

        output_in_table(view, tablefmt='plain')
        if details:
            print()
            print(json.dumps(task, indent=2))

        if log:
            log_path = LOG_FILE.format(f'{task["run_id"]}/task_{task_id}.log')
            print()
            import requests
            for index, line in enumerate(requests.get(log_path).content.decode('utf-8').split('\n')):
                print(f' {index}\t{line}')

        if recording:
            print()
            download_recording(task, recording_az_mode)

        print()
        print()
