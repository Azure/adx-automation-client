# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import sys
import argparse
import functools
import shlex
import logging
import datetime
from subprocess import check_output, CalledProcessError
from collections import defaultdict

import requests
import tabulate

logger = logging.getLogger('A01')

LOG_FILE = 'https://azureclia01log.file.core.windows.net/k8slog/{}?' \
           'se=2019-01-01T00%3A00%3A00Z&sp=r&sv=2017-04-17&sr=s&sig=v/4afGXPe5ENN1K7zIw1oQVUm73LDCZPEFgp6NUerh4%3D'


@functools.lru_cache(maxsize=1)
def get_store_uri(store) -> str:
    cmd = f'kubectl get service {store}' + ' -ojsonpath={.status.loadBalancer.ingress[0].ip}'
    try:
        store_ip = check_output(shlex.split(cmd)).decode('utf-8')
        return f'http://{store_ip}'
    except CalledProcessError:
        logger.error('Failed to get the a01 task store service URI. Make sure kubectl is installed and login the '
                     'cluster.')
        sys.exit(1)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='a01')
    parser.set_defaults(func=lambda _: parser.print_help())
    sub = parser.add_subparsers(title='Commands')

    get_actions = sub.add_parser('get', help='Retrieve information.')
    get_actions.set_defaults(func=lambda _: get_actions.print_help())
    get_actions_root = get_actions.add_subparsers(title='Sub Commands')

    get_run = get_actions_root.add_parser('run', help='Retrieve run data.')
    get_run.add_argument('id', help='The run id')
    get_run.add_argument('--store', help='The name of the task store. Default: a01store.', default='a01store')
    get_run.set_defaults(func=list_run)

    get_task = get_actions_root.add_parser('task', help='Retrieve task data.')
    get_task.add_argument('id', help='The task id. Support multiple IDs.', nargs='+')
    get_task.add_argument('--store', help='The name of the task store. Default: a01store.', default='a01store')
    get_task.add_argument('--log', help='Retrieve the log of the task', action='store_true')
    get_task.add_argument('--run', help='The run id (required when retrieve log. will be remove later)')
    get_task.set_defaults(func=show_task)

    # if print_help:
    #     parser.print_help()
    return parser.parse_args()


def list_run(args):
    resp = requests.get(f'{get_store_uri(args.store)}/run/{args.id}/tasks')
    resp.raise_for_status()
    tasks = resp.json()

    statuses = defaultdict(lambda: 0)
    results = defaultdict(lambda: 0)

    failure = []

    for task in tasks:
        status = task['status']
        result = task['result']

        statuses[status] = statuses[status] + 1
        results[result] = results[result] + 1

        if result == 'Failed':
            failure.append(
                (task['id'],
                 task['name'].rsplit('.')[-1],
                 task['status'],
                 task['result'],
                 (task.get('result_details') or dict()).get('agent'),
                 (task.get('result_details') or dict()).get('duration')))

    status_summary = ' | '.join([f'{status_name}: {count}' for status_name, count in statuses.items()])
    result_summary = ' | '.join([f'{result or "Not run"}: {count}' for result, count in results.items()])

    summaries = [('Time', str(datetime.datetime.now())), ('Task', status_summary), ('Result', result_summary)]

    print()
    print(tabulate.tabulate(summaries, tablefmt='plain'))
    print()
    print(tabulate.tabulate(failure, headers=('id', 'name', 'status', 'result', 'agent', 'duration(ms)')))


def show_task(args):
    for task_id in args.id:
        resp = requests.get(f'{get_store_uri(args.store)}/task/{task_id}')
        resp.raise_for_status()
        task = resp.json()
        view = [
            ('id', task['id']),
            ('result', task['result']),
            ('test', task['settings']['path']),
            ('duration(ms)', task['result_details']['duration'])
        ]

        print(tabulate.tabulate(view, tablefmt='plain'))
        if args.log:
            log_path = LOG_FILE.format(f'{args.run}/task_{task_id}.log')
            print()
            for index, line in enumerate(requests.get(log_path).content.decode('utf-8').split('\n')):
                print(f' {index}\t{line}')

        print()
        print()


def main() -> None:
    args = get_arguments()
    args.func(args)


if __name__ == '__main__':
    main()
