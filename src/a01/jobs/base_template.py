import abc
from typing import Dict, List, Optional
from kubernetes.client.models.v1_job import V1Job
from kubernetes.client.models.v1_job_spec import V1JobSpec
from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_container import V1Container
from kubernetes.client.models.v1_pod_spec import V1PodSpec
from kubernetes.client.models.v1_pod_template_spec import V1PodTemplateSpec
from kubernetes.client.models.v1_local_object_reference import V1LocalObjectReference
from kubernetes.client.models.v1_volume import V1Volume
from kubernetes.client.models.v1_volume_mount import V1VolumeMount
from kubernetes.client.models.v1_env_var import V1EnvVar
from kubernetes.client.models.v1_env_var_source import V1EnvVarSource
from kubernetes.client.models.v1_object_field_selector import V1ObjectFieldSelector
from kubernetes.client.models.v1_secret_key_selector import V1SecretKeySelector


class JobTemplate(abc.ABC):  # pylint: disable=too-many-instance-attributes
    def __init__(self, name: str, image: str, parallelism: Optional[int], run_id: str) -> None:
        super(JobTemplate, self).__init__()
        self.name = name
        self.image = image
        self.parallelism = parallelism
        self.run_id = str(run_id)
        self.labels = {'run_id': str(run_id)}

        self.backoff_limit = 5
        self.start_command = ['python', '/app/job.py']
        self.images_pull_secrets = 'azureclidev-acr'

        self.environment_variables = self.get_default_environment_variables()
        self.environment_variables.extend(self.create_environments() or [])
        self.volumes = self.create_volumes()

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
            backoff_limit=self.backoff_limit,
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
        main_container = V1Container(name=f'main', image=self.image)

        if self.start_command:
            main_container.command = self.start_command

        if self.volumes:
            volume_mounts = []
            for mount_path, volume in self.volumes.items():
                volume_mounts.append(V1VolumeMount(mount_path=mount_path, name=volume.name))
            main_container.volume_mounts = volume_mounts

        if self.environment_variables:
            main_container.env = self.environment_variables

        # This assume only one container is required.
        return [main_container]

    def get_volumes(self) -> Optional[List[V1Volume]]:
        return list(self.volumes.values()) if self.volumes else None

    def get_default_environment_variables(self) -> List[V1EnvVar]:  # pylint: disable=invalid-name
        return [
            V1EnvVar(name='ENV_POD_NAME',
                     value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='metadata.name'))),
            V1EnvVar(name='ENV_NODE_NAME',
                     value_from=V1EnvVarSource(field_ref=V1ObjectFieldSelector(field_path='spec.nodeName'))),
            V1EnvVar(name='A01_DROID_RUN_ID', value=self.run_id),
            V1EnvVar(name='A01_STORE_NAME', value='task-store-web-service-internal'),
            V1EnvVar(name='A01_INTERNAL_COMKEY', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(name='a01store-internal-communication-key', key='key')))
        ]

    @abc.abstractmethod
    def create_volumes(self) -> Optional[Dict[str, V1Volume]]:
        """Return a mountPath -> volume map for customization. Otherwise returns None."""
        return None

    @abc.abstractmethod
    def create_environments(self) -> Optional[List[V1EnvVar]]:
        """Return environment variable settings. Otherwise return None."""
        return None
