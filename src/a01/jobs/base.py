from typing import List, Optional
from kubernetes.client.models.v1_job import V1Job
from kubernetes.client.models.v1_job_spec import V1JobSpec
from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_container import V1Container
from kubernetes.client.models.v1_pod_spec import V1PodSpec
from kubernetes.client.models.v1_pod_template_spec import V1PodTemplateSpec
from kubernetes.client.models.v1_local_object_reference import V1LocalObjectReference
from kubernetes.client.models.v1_volume import V1Volume
from kubernetes.client.models.v1_volume_mount import V1VolumeMount
from kubernetes.client.models.v1_azure_file_volume_source import V1AzureFileVolumeSource
from kubernetes.client.models.v1_env_var import V1EnvVar
from kubernetes.client.models.v1_env_var_source import V1EnvVarSource
from kubernetes.client.models.v1_object_field_selector import V1ObjectFieldSelector
from kubernetes.client.models.v1_secret_key_selector import V1SecretKeySelector

from a01.docker.droid_image import DroidImage

BACKOFF_LIMIT = 5


class JobTemplate(object):  # pylint: disable=too-many-instance-attributes
    def __init__(self, name: str, image: DroidImage, run_id: str,  # pylint: disable=too-many-arguments
                 parallelism: Optional[int], live: bool = False, secret_name: str = None, mode: str = None) -> None:
        self.name = name
        self.image = image
        self.parallelism = parallelism
        self.run_id = str(run_id)
        self.labels = {'run_id': str(run_id), 'run_live': str(live)}
        self.secret = secret_name or image.product_name

        self.live = live
        self.mode = mode

        self.images_pull_secrets = 'azureclidev-acr'
        self.environment_variables = self.get_environment_variables()

        self.mount_share = 'k8slog'

    def get_body(self) -> V1Job:
        return V1Job(
            api_version='batch/v1',
            kind='Job',
            metadata=self.get_metadata(),
            spec=self.get_spec())

    def get_metadata(self) -> V1ObjectMeta:
        return V1ObjectMeta(name=self.name, labels=self.labels)

    def get_spec(self) -> V1JobSpec:
        return V1JobSpec(
            parallelism=self.parallelism,
            backoff_limit=BACKOFF_LIMIT,
            template=self.get_template()
        )

    def get_template(self) -> V1PodTemplateSpec:
        return V1PodTemplateSpec(
            metadata=V1ObjectMeta(
                name=f'{self.name}-pod',
                labels=self.labels
            ),
            spec=self.get_pod_spec())

    def get_pod_spec(self) -> V1PodSpec:
        return V1PodSpec(
            containers=self.get_containers(),
            image_pull_secrets=[V1LocalObjectReference(name=self.images_pull_secrets)],
            restart_policy='Never',
            volumes=self.get_volumes())

    def get_containers(self) -> List[V1Container]:
        main_container = V1Container(name=f'main', image=self.image.image_name)

        if self.image.mount_storage:
            main_container.volume_mounts = [V1VolumeMount(mount_path='/mnt/storage', name='azure-storage')]

        if self.environment_variables:
            main_container.env = self.environment_variables

        # This assume only one container is required.
        return [main_container]

    def get_volumes(self) -> Optional[List[V1Volume]]:
        if self.image.mount_storage:
            return [V1Volume(name='azure-storage', azure_file=V1AzureFileVolumeSource(secret_name=self.secret,
                                                                                      share_name=self.mount_share))]
        return None

    def get_environment_variables(self) -> List[V1EnvVar]:
        result = [
            V1EnvVar(name='ENV_POD_NAME',
                     value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='metadata.name'))),
            V1EnvVar(name='ENV_NODE_NAME',
                     value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='spec.nodeName'))),
            V1EnvVar(name='A01_DROID_RUN_ID', value=self.run_id),
            V1EnvVar(name='A01_STORE_NAME', value='task-store-web-service-internal/api'),
            V1EnvVar(name='A01_INTERNAL_COMKEY', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(name='a01store', key='internal.key')))
        ]

        for name, key in self.image.secret_to_env.items():
            result.append(V1EnvVar(name=name, value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(name=self.secret, key=key))))

        if self.live:
            name, value = self.image.live_env
            if name and value:
                result.append(V1EnvVar(name=name, value=value))

        if self.mode:
            name = self.image.mode_env
            if name:
                result.append(V1EnvVar(name=name, value=self.mode))

        return result
