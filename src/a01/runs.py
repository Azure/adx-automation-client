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
import docker
import docker.errors
from requests import HTTPError

from a01.common import get_logger, download_recording, IS_WINDOWS, A01Config
from a01.tasks import get_task
from a01.cli import cmd, arg
from a01.communication import session
from a01.auth import get_user_id

logger = get_logger(__name__)  # pylint: disable=invalid-name


@cmd('get runs', desc='Retrieve the runs.')
def get_runs() -> None:
    config = A01Config()
    resp = session.get(f'{config.endpoint_uri}/runs')
    resp.raise_for_status()
    view = [(run['id'], run['name'], run['creation'], run['details'].get('remark', '')) for run in resp.json()]
    print()
    print(tabulate.tabulate(view, headers=('id', 'name', 'creation', 'remark')))


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
    config = A01Config()
    resp = session.get(f'{config.endpoint_uri}/run/{run_id}/tasks')
    if resp.status_code == 404:
        print(f'Run {run_id} is not found.')
        sys.exit(1)

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

        if result != 'Passed':
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
@arg('from_failures', option=['--from-failures'], help='Create the run base on the failed tasks of another run')
@arg('path_prefix', option=['--prefix'], help='Filter the task base on the test path prefix')
@arg('live', help='Run test live')
@arg('sp_secret', option=('--sp', '--service-principal-secret'),
     help='The kubernete secret represents the service principal for live test.')
@arg('storage_secret', option=('--storage', '--log-storage-secret'),
     help='The kubernete secret represents the Azure Storage Account credential for logging')
@arg('query', help='The regular expression used to query the tests.')
@arg('remark', help='The addition information regarding to this run. Specify "official" will trigger an email '
                    'notification to the entire team after the job finishes.')
@arg('email', help='Send an email to you after the job finishes.')
# pylint: disable=too-many-arguments, too-many-locals
def create_run(image: str,
               path_prefix: str = None, from_failures: str = None, dry_run: bool = False, live: bool = False,
               parallelism: int = 3, sp_secret: str = 'azurecli-live-sp', storage_secret: str = 'azurecli-test-storage',
               query: str = None, remark: str = None, email: bool = False) -> None:
    job_name = f'azurecli-test-{base64.b32encode(os.urandom(12)).decode("utf-8").lower()}'.rstrip('=')
    remark = remark or ''
    config = A01Config()
    config.ensure_config()

    @functools.lru_cache(maxsize=1)
    def get_tasks_from_image() -> typing.List[dict]:
        docker_client = docker.from_env()

        try:
            try:
                output = docker_client.containers.run(image=image, command=['/app/get_index'], remove=True)
            except (docker.errors.ContainerError, docker.errors.APIError):
                # This form of test listing mechanism is going to retire
                output = docker_client.containers.run(image=image, command=['python', '/app/collect_tests.py'],
                                                      remove=True)

            tests = json.loads(output)
            if query:
                tests = [t for t in tests if re.match(query, t['path'])]

            return tests

        except docker.errors.ContainerError:
            logger.exception('Fail to collect tests in the container.')
            sys.exit(1)
        except docker.errors.ImageNotFound:
            logger.exception(f'Image {image} not found.')
            sys.exit(1)
        except docker.errors.APIError:
            logger.exception('Docker operation failed.')
            sys.exit(1)
        except (json.JSONDecodeError, TypeError):
            logger.exception('Failed to parse the manifest as JSON.')
            sys.exit(1)

    def select_tasks(prefix: str) -> typing.List[dict]:
        candidates = get_tasks_from_image()

        if prefix:
            candidates = [candidate for candidate in candidates if candidate['path'].startswith(prefix)]

        if from_failures:
            all_tasks = session.get(f'{config.endpoint_uri}/run/{from_failures}/tasks').json()
            failed_test_paths = set([task['settings']['path'] for task in all_tasks if task['result'] != 'Passed'])
            candidates = [candidate for candidate in candidates if candidate['path'] in failed_test_paths]

        return candidates

    def post_run(store_uri: str) -> str:
        try:
            resp = session.post(f'{store_uri}/run', json={
                'name': f'Azure CLI Test @ {image}',
                'settings': {
                    'droid_image': image,
                },
                'details': {
                    'creator': os.environ.get('USER', os.environ.get('USERNAME', 'Unknown')),
                    'client': 'A01 CLI',
                    'live': str(live),
                    'remark': remark
                }
            })
            return resp.json()['id']
        except HTTPError:
            logger.exception('Failed to create run in the task store.')
            sys.exit(1)
        except (json.JSONDecodeError, TypeError):
            logger.exception('Failed to deserialize the response content.')
            sys.exit(1)

    def post_tasks(tasks: typing.List[dict], run_id: str, store_uri: str) -> str:
        try:
            task_payload = [
                {
                    'name': f'Test: {task["path"]}',
                    'annotation': image,
                    'settings': {
                        'path': task['path'],
                    }
                } for task in tasks]
            session.post(f'{store_uri}/run/{run_id}/tasks', json=task_payload).raise_for_status()
        except HTTPError:
            logger.exception('Failed to create tasks in the task store.')
            sys.exit(1)
        return run_id

    def config_job(run_id: str) -> dict:
        environment_variables = [
            {'name': 'ENV_POD_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.name'}}},
            {'name': 'ENV_NODE_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'spec.nodeName'}}},
            {'name': 'A01_DROID_RUN_ID', 'value': str(run_id)},
            {'name': 'A01_STORE_NAME', 'value': 'task-store-web-service-internal'},
            {'name': 'A01_INTERNAL_COMKEY',
             'valueFrom': {'secretKeyRef': {'name': 'a01store-internal-communication-key', 'key': 'key'}}}
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
                'name': job_name,
                'labels': {
                    'run_id': str(run_id),
                    'run_live': str(live)
                }
            },
            'spec': {
                'parallelism': parallelism,
                'backoffLimit': 5,
                'template': {
                    'metadata': {
                        'name': f'{job_name}-droid',
                        'labels': {
                            'run_id': str(run_id),
                            'run_live': str(live)
                        }
                    },
                    'spec': {
                        'containers': [{
                            'name': 'droid',
                            'image': image,
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

    def config_monitor_job(run_id: str) -> dict:
        environments = [{'name': 'A01_MONITOR_RUN_ID', 'value': str(run_id)},
                        {'name': 'A01_MONITOR_INTERVAL', 'value': '30'},
                        {'name': 'A01_STORE_NAME', 'value': 'task-store-web-service-internal'},
                        {'name': 'A01_INTERNAL_COMKEY', 'valueFrom': {
                            'secretKeyRef': {'name': 'a01store-internal-communication-key', 'key': 'key'}}}]
        if email or remark.lower() == 'official':
            environments.extend([
                {'name': 'A01_REPORT_SMTP_SERVER',
                 'valueFrom': {'secretKeyRef': {'name': 'azurecli-email', 'key': 'server'}}},
                {'name': 'A01_REPORT_SENDER_ADDRESS',
                 'valueFrom': {'secretKeyRef': {'name': 'azurecli-email', 'key': 'username'}}},
                {'name': 'A01_REPORT_SENDER_PASSWORD',
                 'valueFrom': {'secretKeyRef': {'name': 'azurecli-email', 'key': 'password'}}}])

            if remark.lower() == 'official':
                environments.append({'name': 'A01_REPORT_RECEIVER',
                                     'valueFrom': {
                                         'configMapKeyRef': {'name': 'azurecli-config', 'key': 'official.email'}}})
            elif email:
                environments.append({'name': 'A01_REPORT_RECEIVER', 'value': get_user_id()})

        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f'{job_name}-monitor',
                "labels": {
                    'run_id': str(run_id)
                }
            },
            "spec": {
                'template': {
                    'metadata': {
                        'name': f'{job_name}-monitor-pod',
                        'labels': {
                            'run_id': str(run_id)
                        }
                    },
                    'spec': {
                        'containers': [{
                            'name': 'monitor',
                            'image': 'azureclidev.azurecr.io/a01monitor:latest',
                            'env': environments
                        }],
                        'imagePullSecrets': [
                            {'name': 'azureclidev-acr'}
                        ],
                        'restartPolicy': 'Never'
                    }
                }
            }
        }

    def post_job(config: dict) -> None:
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

    selected_tasks = select_tasks(path_prefix)

    run_name = post_tasks(selected_tasks, post_run(config.endpoint_uri), config.endpoint_uri) if not dry_run else '555'

    job_config = config_job(run_name)
    monitor_config = config_monitor_job(run_name)

    if dry_run:
        for index, each in enumerate(selected_tasks):
            print(f' {index + 1}\t{each["path"]}')

        print()
        print(yaml.dump(job_config, default_flow_style=False))
        print()
        print(yaml.dump(monitor_config, default_flow_style=False))
    else:
        post_job(job_config)
        post_job(monitor_config)
        print(json.dumps({'run': run_name, 'job': job_name, 'monitor': f'{job_name}-monitor'}, indent=2))


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
def delete_run(run_id: str) -> None:
    config = A01Config()
    resp = session.delete(f'{config.endpoint_uri}/run/{run_id}')
    resp.raise_for_status()
