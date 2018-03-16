# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import os
import base64

from kubernetes import config as kube_config
from kubernetes import client as kube_client
from kubernetes.client import V1ObjectFieldSelector
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
from kubernetes.client.models.v1_volume_mount import V1VolumeMount
from kubernetes.client.models.v1_volume import V1Volume
from kubernetes.client.models.v1_azure_file_volume_source import V1AzureFileVolumeSource

from a01.common import NAMESPACE
from a01.models import Run


def clean_up_jobs(run: Run) -> None:
    print(f'Deleting obsoleted jobs of run {run.id} ...')

    kube_config.load_kube_config()
    api = kube_client.BatchV1Api()
    api.delete_collection_namespaced_job(namespace=NAMESPACE, label_selector=f"run_id={run.id}")

    job_name = run.details.get('a01.reserved.jobname', None)
    if job_name:
        api.delete_collection_namespaced_job(namespace=NAMESPACE, label_selector=f"job-name={job_name}")


def create_controller_job(run: Run) -> V1Job:
    print(f'Create new controller job for run {run.id} ...')

    random_tag = base64.b32encode(os.urandom(4)).decode("utf-8").lower().rstrip('=')
    ctrl_job_name = f'ctrl-{run.id}-{random_tag}'
    labels = {'run_id': str(run.id), 'run_live': str(run.settings['a01.reserved.livemode'] == str(True))}
    image = run.settings['a01.reserved.imagename']
    agent = run.settings['a01.reserved.agentver']

    kube_config.load_kube_config()
    api = kube_client.BatchV1Api()

    return api.create_namespaced_job(
        namespace=NAMESPACE,
        body=V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=V1ObjectMeta(name=ctrl_job_name, labels=labels),
            spec=V1JobSpec(
                backoff_limit=3,
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(name=ctrl_job_name, labels=labels),
                    spec=V1PodSpec(
                        containers=[V1Container(
                            name='main',
                            image=image,
                            command=['/mnt/agents/a01dispatcher', '-run', str(run.id)],
                            env=[
                                V1EnvVar(name='A01_INTERNAL_COMKEY', value_from=V1EnvVarSource(
                                    secret_key_ref=V1SecretKeySelector(name='store-secrets', key='comkey'))),
                                V1EnvVar(name='ENV_POD_NAME', value_from=V1EnvVarSource(
                                    field_ref=V1ObjectFieldSelector(field_path='metadata.name')))
                            ],
                            volume_mounts=[
                                V1VolumeMount(mount_path='/mnt/agents', name='agents-storage', read_only=True)
                            ]
                        )],
                        image_pull_secrets=[V1LocalObjectReference(name='azureclidev-registry')],
                        volumes=[V1Volume(name='agents-storage',
                                          azure_file=V1AzureFileVolumeSource(read_only=True,
                                                                             secret_name='agent-secrets',
                                                                             share_name=f'linux-{agent}'))],
                        restart_policy='Never')
                )
            )))
