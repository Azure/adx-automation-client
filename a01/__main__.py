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
import json
import base64
import os
import typing
import tempfile
from subprocess import check_output, CalledProcessError
from collections import defaultdict

import requests
import tabulate
import yaml

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

    create_actions = sub.add_parser('create', help='Create objects.')
    create_actions.set_defaults(func=lambda _: create_actions.print_help())
    create_actions_root = create_actions.add_subparsers(title='Sub Commands')

    create_run = create_actions_root.add_parser('run', help='Create a new run')
    create_run.add_argument('image', help='The droid image to run.')
    create_run.add_argument('-p', dest='parallelism', type=int, default=3,
                            help='The number of job to run in parallel. Can be scaled later through kubectl.')
    create_run.add_argument('--dry-run', help='List the tasks instead of actually schedule a run.', action='store_true')
    create_run.add_argument('--from-failures', help='Create the run base on the failed tasks of another run')
    create_run.add_argument('--store', help='The name of the task store. Default: a01store.', default='a01store')
    create_run.add_argument('--path-prefix', help='Filter the task base on the test path prefix')
    create_run.add_argument('--live', help='Run test live', action='store_true')
    create_run.add_argument('--service-principal-secret', default='azurecli-live-sp', dest='sp_secret',
                            help='The kubernetes secret providing service principal.')
    create_run.add_argument('--log-storage-secret', default='azurecli-test-storage', dest='storage_secret',
                            help='The kubernetes secret providing Azure Storage Account credential for logging')
    create_run.set_defaults(func=schedule_run)

    return parser.parse_args()


def schedule_run(args) -> None:
    @functools.lru_cache(maxsize=1)
    def get_tasks_from_image(image_name: str) -> typing.List[dict]:
        temp_container_name = base64.b32encode(os.urandom(12))[:-4]
        run_cmd = f'docker run --name {temp_container_name} {image_name} python /app/collect_tests.py'
        rm_cmd = f'docker rm {temp_container_name}'
        try:
            output = check_output(shlex.split(run_cmd))
            check_output(shlex.split(rm_cmd))
            return json.loads(output)
        except CalledProcessError:
            logger.exception(f'Failed to list tests in image {image_name}.')
            sys.exit(1)
        except (json.JSONDecodeError, TypeError):
            logger.exception('Failed to parse the manifest as JSON.')
            sys.exit(1)

    def select_tasks(image_name: str, from_failures: str, prefix: str, store: str) -> typing.List[dict]:
        candidates = get_tasks_from_image(image_name)

        if prefix:
            candidates = [each for each in candidates if each['path'].startswith(prefix)]

        if from_failures:
            all_tasks = requests.get(f'{get_store_uri(store)}/run/{from_failures}/tasks').json()
            failed_test_paths = set([task['settings']['path'] for task in all_tasks if task['result'] != 'Passed'])
            candidates = [each for each in candidates if each['path'] in failed_test_paths]

        return candidates

    def post_run(store_uri: str, image_name: str) -> str:
        try:
            resp = requests.post(f'{store_uri}/run', json={
                'name': f'Azure CLI Test @ {image_name}',
                'settings': {
                    'droid_image': image_name
                },
                'details': {
                    'creator': os.environ.get('USER', 'Unknown'),
                    'client': 'A01 CLI'
                }
            })
            return resp.json()['id']
        except requests.HTTPError:
            logger.exception('Failed to create run in the task store.')
            sys.exit(1)
        except (json.JSONDecodeError, TypeError):
            logger.exception('Failed to deserialize the response content.')
            sys.exit(1)

    def post_tasks(tasks: typing.List[dict], run_id: str, image_name: str, store_uri: str) -> str:
        try:
            task_payload = [
                {
                    'name': f'Test: {each["path"]}',
                    'annotation': image_name,
                    'settings': {
                        'path': each['path'],
                    }
                } for each in tasks]
            requests.post(f'{store_uri}/run/{run_id}/tasks', json=task_payload).raise_for_status()
        except requests.HTTPError:
            logger.exception('Failed to create tasks in the task store.')
            sys.exit(1)
        return run_id

    def config_job(parallelism: int, image_name: str, run_id: str, live: bool, storage_secret: str,
                   sp_secret: str) -> dict:
        job = f'azurecli-test-{base64.b32encode(os.urandom(12)).decode("utf-8").lower()}'.rstrip('=')

        environment_variables = [
            {'name': 'ENV_POD_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.name'}}},
            {'name': 'ENV_NODE_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'spec.nodeName'}}},
            {'name': 'A01_DROID_RUN_ID', 'value': str(run_id)}
        ]
        if live:
            environment_variables.append({'name': 'A01_RUN_LIVE', 'value': 'True'})
            environment_variables.append(
                {'name': 'A01_SP_USERNAME', 'valueFrom': {'secretKeyRef': {'name': sp_secret, 'key': 'username'}}})
            environment_variables.append(
                {'name': 'A01_SP_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': sp_secret, 'key': 'password'}}})
            environment_variables.append(
                {'name': 'A01_SP_TENANT', 'valueFrom': {'secretKeyRef': {'name': sp_secret, 'key': 'tenant'}}})

        return {
            'apiVersion': 'batch/v1',
            'kind': 'Job',
            'metadata': {
                'name': job
            },
            'spec': {
                'parallelism': parallelism,
                'backoffLimit': 5,
                'template': {
                    'metadata': {
                        'name': job
                    },
                    'spec': {
                        'containers': [{
                            'name': 'droid',
                            'image': image_name,
                            'command': ['python', '/app/job.py'],
                            'volumeMounts': [
                                {'name': 'azure-storage', 'mountPath': '/mnt/storage'}
                            ],
                            'env': environment_variables
                        }],
                        'restartPolicy': 'Never',
                        'volumes': [{
                            'name': 'azure-storage',
                            'azureFile': {
                                'secretName': storage_secret,
                                'shareName': 'k8slog',
                            }}]
                    }
                }
            }
        }

    def post_job(config: dict) -> str:
        _, config_file = tempfile.mkstemp(text=True)
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info(f'Temp config file saved at {config_file}')

        try:
            check_output(shlex.split(f'kubectl create -f {config_file}'))
        except CalledProcessError:
            logger.exception(f'Failed to create job.')
            sys.exit(1)

        return config['metadata']['name']

    selected_tasks = select_tasks(args.image, args.from_failures, args.path_prefix, args.store)

    run_name = post_tasks(selected_tasks,
                          post_run(get_store_uri(args.store), args.image),
                          args.image,
                          get_store_uri(args.store)) if not args.dry_run else 'example_run'

    job_config = config_job(args.parallelism, args.image, run_name, args.live, args.storage_secret, args.sp_secret)

    job_name = post_job(job_config) if not args.dry_run else 'example_job'

    if args.dry_run:
        for index, each in enumerate(selected_tasks):
            print(f' {index + 1}\t{each["path"]}')

        print()
        print(yaml.dump(job_config, default_flow_style=False))

    print(json.dumps({'run': run_name, 'job': job_name}))


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
