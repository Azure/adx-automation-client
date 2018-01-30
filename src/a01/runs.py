import datetime
import base64
import functools
import json
import shlex
import sys
import os
import typing
import tempfile
import re
from collections import defaultdict
from subprocess import check_output, CalledProcessError

import tabulate
import yaml
from requests import HTTPError

from a01.common import get_store_uri, get_logger, download_recording, IS_WINDOWS
from a01.tasks import get_task
from a01.cli import cmd, arg
from a01.communication import session

logger = get_logger(__name__)  # pylint: disable=invalid-name


@cmd('get runs', desc='Retrieve the runs.')
def get_runs() -> None:
    resp = session.get(f'{get_store_uri()}/runs')
    resp.raise_for_status()
    view = [(run['id'], run['name'], run['creation']) for run in resp.json()]
    print()
    print(tabulate.tabulate(view, headers=('id', 'name', 'creation')))


@cmd('get run', desc='Retrieve a run')
@arg('run_id', help='The run id.', positional=True)
@arg('log', help="Include the failed tasks' logs.", option=('-l', '--log'))
@arg('recording', option=('-r', '--recording'),
     help='Download the recording files in recording directory at current working directory. The recordings '
          'are flatten with the full test path as the file name if --az-mode is not specified. If --az-mode is '
          'set, the recording files are arranged in directory structure mimic Azure CLI source code.')
@arg('recording_az_mode', option=['--az-mode'],
     help='When download the recording files the files are arranged in directory structure mimic Azure CLI '
          'source code.')
def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False) -> None:
    resp = session.get(f'{get_store_uri()}/run/{run_id}/tasks')
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

    if log:
        print()
        print('Task details:')
        print()
        get_task(ids=[f[0] for f in failure], log=True)

    if recording:
        print()
        print('Download recordings ...')
        for task in tasks:
            download_recording(task, recording_az_mode)


@cmd('create run', desc='Create a new run.')
@arg('image', help='The droid image to run.', positional=True)
@arg('parallelism', option=('-p', '--parallelism'),
     help='The number of job to run in parallel. Can be scaled later through kubectl.')
@arg('dry_run', option=('--dryrun', '--dry-run'), help='List the tasks instead of actually schedule a run.',
     action='store_true')
@arg('from_failures', help='Create the run base on the failed tasks of another run')
@arg('path_prefix', help='Filter the task base on the test path prefix')
@arg('live', help='Run test live')
@arg('sp_secret', option=('--sp', '--service-principal-secret'),
     help='The kubernete secret represents the service principal for live test.')
@arg('storage_secret', option=('--storage', '--log-storage-secret'),
     help='The kubernete secret represents the Azure Storage Account credential for logging')
@arg('query', help='The regular expression used to query the tests.')
def schedule_run(image: str,  # pylint: disable=too-many-arguments
                 path_prefix: str = None, from_failures: str = None, dry_run: bool = False,
                 live: bool = False, parallelism: int = 3, sp_secret: str = 'azurecli-live-sp',
                 storage_secret: str = 'azurecli-test-storage',
                 query: str = None) -> None:
    @functools.lru_cache(maxsize=1)
    def get_tasks_from_image(image_name: str) -> typing.List[dict]:
        temp_container_name = base64.b32encode(os.urandom(12))[:-4]
        run_cmd = f'docker run --name {temp_container_name} {image_name} python /app/collect_tests.py'
        rm_cmd = f'docker rm {temp_container_name}'
        try:
            output = check_output(shlex.split(run_cmd, posix=not IS_WINDOWS), shell=IS_WINDOWS)
            check_output(shlex.split(rm_cmd, posix=not IS_WINDOWS), shell=IS_WINDOWS)
            tests = json.loads(output)
            if query:
                tests = [t for t in tests if re.match(query, t['path'])]

            return tests
        except CalledProcessError:
            logger.exception(f'Failed to list tests in image {image_name}.')
            sys.exit(1)
        except (json.JSONDecodeError, TypeError):
            logger.exception('Failed to parse the manifest as JSON.')
            sys.exit(1)

    def select_tasks(image_name: str, from_failures: str, prefix: str) -> typing.List[dict]:
        candidates = get_tasks_from_image(image_name)

        if prefix:
            candidates = [candidate for candidate in candidates if candidate['path'].startswith(prefix)]

        if from_failures:
            all_tasks = session.get(f'{get_store_uri()}/run/{from_failures}/tasks').json()
            failed_test_paths = set([task['settings']['path'] for task in all_tasks if task['result'] != 'Passed'])
            candidates = [candidate for candidate in candidates if candidate['path'] in failed_test_paths]

        return candidates

    def post_run(store_uri: str, image_name: str) -> str:
        try:
            resp = session.post(f'{store_uri}/run', json={
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
        except HTTPError:
            logger.exception('Failed to create run in the task store.')
            sys.exit(1)
        except (json.JSONDecodeError, TypeError):
            logger.exception('Failed to deserialize the response content.')
            sys.exit(1)

    def post_tasks(tasks: typing.List[dict], run_id: str, image_name: str, store_uri: str) -> str:
        try:
            task_payload = [
                {
                    'name': f'Test: {task["path"]}',
                    'annotation': image_name,
                    'settings': {
                        'path': task['path'],
                    }
                } for task in tasks]
            session.post(f'{store_uri}/run/{run_id}/tasks', json=task_payload).raise_for_status()
        except HTTPError:
            logger.exception('Failed to create tasks in the task store.')
            sys.exit(1)
        return run_id

    def config_job(parallelism: int,  # pylint: disable=too-many-arguments
                   image_name: str, run_id: str, live: bool, storage_secret: str, sp_secret: str) -> dict:
        job = f'azurecli-test-{base64.b32encode(os.urandom(12)).decode("utf-8").lower()}'.rstrip('=')

        environment_variables = [
            {'name': 'ENV_POD_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.name'}}},
            {'name': 'ENV_NODE_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'spec.nodeName'}}},
            {'name': 'A01_DROID_RUN_ID', 'value': str(run_id)},
            {'name': 'A01_STORE_NAME', 'value': 'task-store-web-service-internal'}
        ]
        if live:
            environment_variables.append({'name': 'A01_RUN_LIVE', 'value': 'True'})
            environment_variables.append(
                {'name': 'A01_SP_USERNAME', 'valueFrom': {'secretKeyRef': {'name': sp_secret, 'key': 'username'}}})
            environment_variables.append(
                {'name': 'A01_SP_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': sp_secret, 'key': 'password'}}})
            environment_variables.append(
                {'name': 'A01_SP_TENANT', 'valueFrom': {'secretKeyRef': {'name': sp_secret, 'key': 'tenant'}}})
            environment_variables.append(
                {'name': 'A01_INTERNAL_COMKEY',
                 'valueFrom': {'secretKeyRef': {'name': 'a01store-internal-communication-key', 'key': 'key'}}})

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
                        'imagePullSecrets': [
                            {'name': 'azureclidev-acr'}
                        ],
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
        with open(config_file, 'w') as config_file_handle:
            yaml.dump(config, config_file_handle, default_flow_style=False)
        logger.info(f'Temp config file saved at {config_file}')

        try:
            check_output(shlex.split(f'kubectl create -f {config_file} --namespace az', posix=not IS_WINDOWS),
                         shell=IS_WINDOWS)
        except CalledProcessError:
            logger.exception(f'Failed to create job.')
            sys.exit(1)

        return config['metadata']['name']

    selected_tasks = select_tasks(image, from_failures, path_prefix)

    run_name = post_tasks(selected_tasks,
                          post_run(get_store_uri(), image),
                          image,
                          get_store_uri()) if not dry_run else 'example_run'

    job_config = config_job(parallelism, image, run_name, live, storage_secret, sp_secret)

    job_name = post_job(job_config) if not dry_run else 'example_job'

    if dry_run:
        for index, each in enumerate(selected_tasks):
            print(f' {index + 1}\t{each["path"]}')

        print()
        print(yaml.dump(job_config, default_flow_style=False))

    print(json.dumps({'run': run_name, 'job': job_name}))


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('ids', help='Ids of the run to be deleted.', positional=True)
def delete_run(ids: typing.List[str]) -> None:
    for each in ids:
        resp = session.delete(f'{get_store_uri()}/run/{each}')
        resp.raise_for_status()
