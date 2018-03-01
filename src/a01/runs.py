import base64
import json
import sys
import os
from itertools import zip_longest

import colorama
from kubernetes import config as kube_config
from kubernetes import client as kube_client
from kubernetes.client import V1ObjectFieldSelector

from kubernetes.client.models.v1_config_map_key_selector import V1ConfigMapKeySelector
from kubernetes.client.models.v1_job import V1Job
from kubernetes.client.models.v1_job_spec import V1JobSpec
from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_container import V1Container
from kubernetes.client.models.v1_pod_spec import V1PodSpec
from kubernetes.client.models.v1_pod_template_spec import V1PodTemplateSpec
from kubernetes.client.models.v1_local_object_reference import V1LocalObjectReference
from kubernetes.client.models.v1_env_var import V1EnvVar
from kubernetes.client.models.v1_env_var_source import V1EnvVarSource
from kubernetes.client.models.v1_secret_key_selector import V1SecretKeySelector

import a01.models
from a01.common import get_logger, A01Config, COMMON_IMAGE_PULL_SECRET
from a01.cli import cmd, arg
from a01.communication import session
from a01.auth import get_user_id
from a01.output import output_in_table

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
@arg('raw', help='For debug.')
def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False,
            show_all: bool = False, raw: bool = False) -> None:
    try:
        tasks = a01.models.TaskCollection.get(run_id=run_id)
        output_in_table(tasks.get_table_view(failed=not show_all), headers=tasks.get_table_header())
        output_in_table(tasks.get_summary(), tablefmt='plain')

        log_path_template = None
        if log or recording:
            run = a01.models.Run.get(run_id=run_id)
            log_path_template = run.get_log_path_template()

        if log:
            for failure in tasks.get_failed_tasks():
                output_in_table(zip_longest(failure.get_table_header(), failure.get_table_view()), tablefmt='plain')
                output_in_table(failure.get_log_content(log_path_template), tablefmt='plain',
                                foreground_color=colorama.Fore.CYAN)

            output_in_table(tasks.get_summary(), tablefmt='plain')

        if recording:
            print()
            print('Download recordings ...')
            for task in tasks.tasks:
                task.download_recording(log_path_template, recording_az_mode)

        if raw:
            run = a01.models.Run.get(run_id=run_id)
            print(json.dumps(run.to_dict(), indent=2))
    except ValueError as err:
        logger.error(err)
        sys.exit(1)


@cmd('create run', desc='Create a new run.')
@arg('image', help='The droid image to run.', positional=True)
@arg('parallelism', option=('-p', '--parallelism'),
     help='The number of job to run in parallel. Can be scaled later through kubectl.')
@arg('from_failures', option=['--from-failures'], help='Create the run base on the failed tasks of another run')
@arg('live', help='Run test live')
@arg('mode', help='The mode in which the test is run. The option accept a string which will be passed on to the pod as '
                  'an environment variable. The meaning of the string is open for interpretations.')
@arg('query', help='The regular expression used to query the tests.')
@arg('remark', help='The addition information regarding to this run. Specify "official" will trigger an email '
                    'notification to the entire team after the job finishes.')
@arg('email', help='Send an email to you after the job finishes.')
@arg('secret', help='The name of the secret to be used. Default to the image\'s a01.product label.')
@arg('reset_run', option=['--reset-run'], help='Reset a run')
# pylint: disable=too-many-arguments, too-many-locals
def create_run(image: str, from_failures: str = None, live: bool = False, parallelism: int = 3, query: str = None,
               remark: str = '', email: bool = False, secret: str = None, mode: str = None,
               reset_run: str = None) -> None:
    remark = remark or ''
    try:
        if not reset_run:
            run_model = a01.models.Run(name=f'Azure CLI Test @ {image}',
                                       settings={
                                           'a01.reserved.imagename': image,
                                           'a01.reserved.imagepullsecret': 'azureclidev-acr',
                                           'a01.reserved.secret': secret,
                                           'a01.reserved.storageshare': 'k8slog',
                                           'a01.reserved.testquery': query,
                                           'a01.reserved.remark': remark,
                                           'a01.reserved.useremail': get_user_id() if email else '',
                                           'a01.reserved.initparallelism': parallelism,
                                           'a01.reserved.livemode': str(live),
                                           'a01.reserved.testmode': mode,
                                           'a01.reserved.fromrunfailure': from_failures,
                                       },
                                       details={
                                           'a01.reserved.creator': get_user_id(),
                                           'a01.reserved.client': 'A01 CLI'
                                       })

            # prune
            to_delete = [k for k, v in run_model.settings.items() if not v]
            for k in to_delete:
                del run_model.settings[k]
            to_delete = [k for k, v in run_model.details.items() if not v]
            for k in to_delete:
                del run_model.details[k]

            run_name = run_model.post()
            print(f'Created: {run_name}')
        else:
            run_name = reset_run
            print(f'Reset: {run_name}')

        # create manage job
        kube_config.load_kube_config()
        api = kube_client.BatchV1Api()

        random_tag = base64.b32encode(os.urandom(4)).decode("utf-8").lower().rstrip('=')
        job_name = f'ctrl-{run_name}-{random_tag}'
        labels = {'run_id': str(run_name), 'run_live': str(live)}

        api.create_namespaced_job(
            namespace='az',
            body=V1Job(
                api_version="batch/v1",
                kind="Job",
                metadata=V1ObjectMeta(name=job_name, labels=labels),
                spec=V1JobSpec(
                    backoff_limit=3,
                    template=V1PodTemplateSpec(
                        metadata=V1ObjectMeta(name=job_name, labels=labels),
                        spec=V1PodSpec(
                            containers=[V1Container(
                                name='main',
                                image=image,
                                command=['/app/a01dispatcher', '-run', str(run_name)],
                                env=[
                                    V1EnvVar(name='A01_STORE_NAME', value='task-store-web-service-internal/api'),
                                    V1EnvVar(name='A01_INTERNAL_COMKEY', value_from=V1EnvVarSource(
                                        secret_key_ref=V1SecretKeySelector(name='a01store', key='internal.key'))),
                                    V1EnvVar(name='ENV_POD_NAME', value_from=V1EnvVarSource(
                                        field_ref=V1ObjectFieldSelector(field_path='metadata.name')))
                                ]
                            )],
                            image_pull_secrets=[V1LocalObjectReference(name=COMMON_IMAGE_PULL_SECRET)],
                            restart_policy='Never')
                    )
                )))

        sys.exit(0)
    except ValueError as ex:
        logger.error(ex)
        sys.exit(1)


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
def delete_run(run_id: str) -> None:
    config = A01Config()
    resp = session.delete(f'{config.endpoint_uri}/run/{run_id}')
    resp.raise_for_status()
