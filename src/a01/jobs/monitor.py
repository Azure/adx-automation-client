from typing import List

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

from a01.models import Run
from a01.common import EMAIL_ACCOUNT_SECRET_NAME, EMAIL_SERVICE_FAIL_RESET_LIMIT, COMMON_IMAGE_PULL_SECRET

MONITOR_IMAGE = 'azureclidev.azurecr.io/a01monitor:latest'


class MonitorTemplate(object):
    def __init__(self, run: Run, interval: int = 30, email: str = None) -> None:
        self.run = run
        self.name = f'a01-monitor-{self.run.id}'
        self.labels = {'run_id': str(run.id), 'run_live': run.details['live']}
        self.official = run.details.get('remark', '').lower() == 'official'

        self.interval = interval
        self.email = email

    def get_body(self) -> V1Job:
        return V1Job(
            api_version='batch/v1',
            kind='Job',
            metadata=self.get_metadata(),
            spec=self.get_spec())

    def get_metadata(self) -> V1ObjectMeta:
        return V1ObjectMeta(name=self.name, labels=self.labels)

    def get_spec(self) -> V1JobSpec:
        return V1JobSpec(backoff_limit=EMAIL_SERVICE_FAIL_RESET_LIMIT, template=self.get_template())

    def get_template(self) -> V1PodTemplateSpec:
        return V1PodTemplateSpec(
            metadata=V1ObjectMeta(name=self.name, labels=self.labels),
            spec=self.get_pod_spec())

    def get_pod_spec(self) -> V1PodSpec:
        return V1PodSpec(
            containers=self.get_containers(),
            image_pull_secrets=[V1LocalObjectReference(name=COMMON_IMAGE_PULL_SECRET)],
            restart_policy='Never')

    def get_containers(self) -> List[V1Container]:
        return [V1Container(name=f'main', image=MONITOR_IMAGE, env=self.get_environment_variables())]

    def get_environment_variables(self) -> List[V1EnvVar]:
        environment = [
            V1EnvVar(name='A01_MONITOR_RUN_ID', value=str(self.run.id)),
            V1EnvVar(name='A01_MONITOR_INTERVAL', value=str(self.interval)),
            V1EnvVar(name='A01_STORE_NAME', value='task-store-web-service-internal/api'),
            V1EnvVar(name='A01_INTERNAL_COMKEY', value_from=V1EnvVarSource(
                secret_key_ref=V1SecretKeySelector(name='a01store', key='internal.key')))
        ]

        if self.email or self.official:
            environment.extend([
                self._map_secret_to_env('A01_REPORT_SMTP_SERVER', 'server'),
                self._map_secret_to_env('A01_REPORT_SENDER_ADDRESS', 'username'),
                self._map_secret_to_env('A01_REPORT_SENDER_PASSWORD', 'password')])

            if self.official:
                environment.append(self._map_config_to_env('A01_REPORT_RECEIVER', 'official.email'))
            elif self.email:
                environment.append(V1EnvVar(name='A01_REPORT_RECEIVER', value=self.email))

        return environment

    @staticmethod
    def _map_secret_to_env(env_name: str, secret_key: str) -> V1EnvVar:
        return V1EnvVar(name=env_name,
                        value_from=V1EnvVarSource(
                            secret_key_ref=V1SecretKeySelector(
                                name=EMAIL_ACCOUNT_SECRET_NAME,
                                key=secret_key)))

    def _map_config_to_env(self, env_name: str, config_key: str) -> V1EnvVar:
        config_name = self.run.details['product']
        return V1EnvVar(name=env_name,
                        value_from=V1EnvVarSource(
                            config_map_key_ref=V1ConfigMapKeySelector(name=config_name, key=config_key)))
