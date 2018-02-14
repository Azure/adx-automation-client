from kubernetes.client.models.v1_config_map_key_selector import V1ConfigMapKeySelector

from typing import List
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


BACKOFF_LIMIT = 5


class MonitorTemplate(object):
    def __init__(self, run_id: str, live: bool = False, interval: int = 30,
                 secret_name: str = 'azurecli-email', config_name: str = 'azurecli-config', email: str = None,
                 official: bool = False) -> None:
        self.image_name = 'azureclidev.azurecr.io/a01monitor:latest'
        self.run_id = str(run_id)
        self.name = f'a01-monitor-{self.run_id}'
        self.labels = {'run_id': str(run_id), 'run_live': str(live)}
        self.secret = secret_name
        self.config = config_name
        self.live = live
        self.images_pull_secrets = 'azureclidev-acr'
        self.interval = interval
        self.email = email
        self.official = official

    def get_body(self) -> V1Job:
        return V1Job(
            api_version='batch/v1',
            kind='Job',
            metadata=self.get_metadata(),
            spec=self.get_spec())

    def get_metadata(self) -> V1ObjectMeta:
        return V1ObjectMeta(name=self.name, labels=self.labels)

    def get_spec(self) -> V1JobSpec:
        return V1JobSpec(backoff_limit=BACKOFF_LIMIT, template=self.get_template())

    def get_template(self) -> V1PodTemplateSpec:
        return V1PodTemplateSpec(
            metadata=V1ObjectMeta(name=self.name, labels=self.labels),
            spec=self.get_pod_spec())

    def get_pod_spec(self) -> V1PodSpec:
        return V1PodSpec(
            containers=self.get_containers(),
            image_pull_secrets=[V1LocalObjectReference(name=self.images_pull_secrets)],
            restart_policy='Never')

    def get_containers(self) -> List[V1Container]:
        return [V1Container(name=f'main', image=self.image_name, env=self.get_environment_variables())]

    def get_environment_variables(self) -> List[V1EnvVar]:
        envs = [
            V1EnvVar(name='A01_MONITOR_RUN_ID', value=self.run_id),
            V1EnvVar(name='A01_MONITOR_INTERVAL', value=str(self.interval)),
            V1EnvVar(name='A01_INTERNAL_COMKEY', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(name='a01store-internal-communication-key', key='key')))
        ]

        if self.email or self.official:
            envs.extend([
                self._map_secret_to_env('A01_REPORT_SMTP_SERVER', 'server'),
                self._map_secret_to_env('A01_REPORT_SENDER_ADDRESS', 'username'),
                self._map_secret_to_env('A01_REPORT_SENDER_PASSWORD', 'password')])

            if self.official:
                envs.append(self._map_config_to_env('A01_REPORT_RECEIVER', 'official.email'))
            elif self.email:
                envs.append(V1EnvVar(name='A01_REPORT_RECEIVER', value=self.email))

        return envs

    def _map_secret_to_env(self, env_name: str, secret_key: str) -> V1EnvVar:
        return V1EnvVar(name=env_name,
                        value_from=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=self.secret, key=secret_key)))

    def _map_config_to_env(self, env_name: str, config_key: str) -> V1EnvVar:
        return V1EnvVar(name=env_name,
                        value_from=V1EnvVarSource(
                            config_map_key_ref=V1ConfigMapKeySelector(name=self.config, key=config_key)))
