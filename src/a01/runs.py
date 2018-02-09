import datetime
import base64
import functools
import json
import sys
import os
import typing
import re
from collections import defaultdict

import docker
import docker.errors
from requests import HTTPError
from kubernetes import config as kube_config
from kubernetes import client as kube_client

import a01.models
from a01.common import get_logger, download_recording, A01Config
from a01.tasks import get_task
from a01.cli import cmd, arg
from a01.communication import session
from a01.auth import get_user_id
from a01.output import output_in_table
from a01.jobs import AzureCliJob, AzureCliMonitorJob
from a01.docker import DroidImage

logger = get_logger(__name__)  # pylint: disable=invalid-name


@cmd('get runs', desc='Retrieve the runs.')
def get_runs() -> None:
    config = A01Config()
    resp = session.get(f'{config.endpoint_uri}/runs')
    resp.raise_for_status()
    view = [(run['id'], run['name'], run['creation'], run['details'].get('remark', '')) for run in resp.json()]
    output_in_table(view, headers=('id', 'name', 'creation', 'remark'))


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

        if result != 'Passed' and status != 'initialized':
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

    output_in_table(summaries, tablefmt='plain')
    output_in_table(failure, headers=('id', 'name', 'status', 'result', 'agent', 'duration(ms)'))

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

    try:
        droid_image = DroidImage(image)
        candidates = droid_image.list_tasks(query=query)

        if path_prefix:
            candidates = [candidate for candidate in candidates if candidate['path'].startswith(path_prefix)]

        if from_failures:
            all_tasks = session.get(f'{config.endpoint_uri}/run/{from_failures}/tasks').json()
            failed_test_paths = set([task['settings']['path'] for task in all_tasks if task['result'] != 'Passed'])
            candidates = [candidate for candidate in candidates if candidate['path'] in failed_test_paths]

        if dry_run:
            for index, each in enumerate(candidates, start=1):
                print(f' {index}\t{each["path"]}')

            sys.exit(0)

        run_model = a01.models.Run(name=f'Azure CLI Test @ {image}',
                                   settings={
                                       'droid_image': image,
                                   },
                                   details={
                                       'creator': os.environ.get('USER', os.environ.get('USERNAME', 'Unknown')),
                                       'client': 'A01 CLI',
                                       'live': str(live),
                                       'remark': remark
                                   })
        run_name = run_model.post(endpoint=config.endpoint_uri)

        tasks = [a01.models.Task(name=f'Test: {c["path"]}', annotation=image, settings={'path': c['path']}) for c in
                 candidates]
        task_collection = a01.models.TaskCollection(tasks=tasks, run_id=run_name)
        task_collection.post(endpoint=config.endpoint_uri)

        kube_config.load_kube_config()
        api = kube_client.BatchV1Api()
        test_job = AzureCliJob(name=job_name, image=image, parallelism=parallelism, run_id=run_name, live=live,
                               storage_secret_name=storage_secret, service_principal_secret_name=sp_secret).get_body()
        monitor_job = AzureCliMonitorJob(name=job_name, image='azureclidev.azurecr.io/a01monitor:latest',
                                         run_id=run_name, email=get_user_id() if email else None,
                                         official=remark.lower() == 'official').get_body()
        api.create_namespaced_job(namespace='az', body=test_job)
        api.create_namespaced_job(namespace='az', body=monitor_job)
        print(json.dumps({'run': run_name, 'job': job_name, 'monitor': f'{job_name}-monitor'}, indent=2))
    except ValueError as ex:
        logger.error(ex)
        sys.exit(1)


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
def delete_run(run_id: str) -> None:
    config = A01Config()
    resp = session.delete(f'{config.endpoint_uri}/run/{run_id}')
    resp.raise_for_status()
