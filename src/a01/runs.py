import base64
import json
import sys
import os
from itertools import zip_longest

import colorama
from kubernetes import config as kube_config
from kubernetes import client as kube_client

import a01.models
from a01.common import get_logger, A01Config
from a01.cli import cmd, arg
from a01.communication import session
from a01.auth import get_user_id
from a01.output import output_in_table
from a01.jobs import JobTemplate, MonitorTemplate
from a01.docker import DroidImage

logger = get_logger(__name__)  # pylint: disable=invalid-name


@cmd('get runs', desc='Retrieve the runs.')
def get_runs() -> None:
    try:
        runs = a01.models.RunCollection.get()
        output_in_table(runs.get_table_view(), headers=runs.get_table_header())
    except ValueError as err:
        logger.error(err)
        sys.exit(1)


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
def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False,
            show_all: bool = False) -> None:
    try:
        tasks = a01.models.TaskCollection.get(run_id=run_id)
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
    except ValueError as err:
        logger.error(err)
        sys.exit(1)


@cmd('create run', desc='Create a new run.')
@arg('image', help='The droid image to run.', positional=True)
@arg('parallelism', option=('-p', '--parallelism'),
     help='The number of job to run in parallel. Can be scaled later through kubectl.')
@arg('dry_run', option=('--dryrun', '--dry-run'), help='List the tasks instead of actually schedule a run.',
     action='store_true')
@arg('from_failures', option=['--from-failures'], help='Create the run base on the failed tasks of another run')
@arg('path_prefix', option=['--prefix'], help='Filter the task base on the test path prefix')
@arg('live', help='Run test live')
@arg('query', help='The regular expression used to query the tests.')
@arg('remark', help='The addition information regarding to this run. Specify "official" will trigger an email '
                    'notification to the entire team after the job finishes.')
@arg('email', help='Send an email to you after the job finishes.')
@arg('skip_kube', option=['--skip-kubernetes'], help='Create tasks in task store without schedule Kubernetes jobs. '
                                                     'It is used mainly in testing scenarios.')
@arg('secret', help='The name of the secret to be used. Default to the image\'s a01.product label.')
# pylint: disable=too-many-arguments
def create_run(image: str,
               path_prefix: str = None, from_failures: str = None, dry_run: bool = False, live: bool = False,
               parallelism: int = 3, query: str = None, remark: str = None, email: bool = False,
               skip_kube: bool = False, secret: str = None) -> None:
    remark = remark or ''
    try:
        droid_image = DroidImage(image)
        job_name = f'{droid_image.product_name}-{base64.b32encode(os.urandom(12)).decode("utf-8").lower()}'.rstrip('=')
        candidates = droid_image.list_tasks(query=query)

        if path_prefix:
            candidates = [c for c in candidates if c['classifier']['identifier'].startswith(path_prefix)]

        if from_failures:
            failed_tasks = set(
                task.settings['identifier'] for task in a01.models.TaskCollection.get(from_failures).get_failed_tasks())
            candidates = [c for c in candidates if c['classifier']['identifier'] in failed_tasks]

        if dry_run:
            for index, each in enumerate(candidates, start=1):
                print(f' {index}\t{each["classifier"]["identifier"]}')

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
        run_name = run_model.post()

        tasks = [a01.models.Task(name=f'Test: {c["classifier"]["identifier"]}', annotation=image, settings=c) for c in
                 candidates]
        task_collection = a01.models.TaskCollection(tasks=tasks, run_id=run_name)
        task_collection.post()

        if skip_kube:
            sys.exit(0)

        kube_config.load_kube_config()
        api = kube_client.BatchV1Api()
        test_job = JobTemplate(name=job_name, run_id=run_name, image=droid_image, parallelism=parallelism,
                               secret_name=secret, live=live).get_body()
        monitor_job = MonitorTemplate(run_id=run_name, live=live, email=get_user_id() if email else None,
                                      official=remark.lower() == 'official').get_body()
        api.create_namespaced_job(namespace='az', body=test_job)
        api.create_namespaced_job(namespace='az', body=monitor_job)
        print(json.dumps({'run': run_name, 'job': job_name, 'monitor': f'a01-monitor-{run_name}'}, indent=2))
    except ValueError as ex:
        logger.error(ex)
        sys.exit(1)


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
def delete_run(run_id: str) -> None:
    config = A01Config()
    resp = session.delete(f'{config.endpoint_uri}/run/{run_id}')
    resp.raise_for_status()
