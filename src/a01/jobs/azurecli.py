from typing import Optional, Dict, List

from kubernetes.client.models.v1_object_meta import V1ObjectMeta
from kubernetes.client.models.v1_env_var import V1EnvVar
from kubernetes.client.models.v1_env_var_source import V1EnvVarSource
from kubernetes.client.models.v1_secret_key_selector import V1SecretKeySelector
from kubernetes.client.models.v1_config_map_key_selector import V1ConfigMapKeySelector
from kubernetes.client.models.v1_volume import V1Volume
from kubernetes.client.models.v1_azure_file_volume_source import V1AzureFileVolumeSource

from a01.common import get_logger
from a01.jobs.base_template import JobTemplate


class AzureCliJob(JobTemplate):
    def __init__(self, name: str, image: str, parallelism: int, run_id: str, storage_secret_name: str,
                 service_principal_secret_name: str, live: bool = False) -> None:
        logger = get_logger(AzureCliJob.__class__.__name__)

        if not storage_secret_name:
            logger.error('The storage secret name is not given.')
            raise ValueError()

        if live and not service_principal_secret_name:
            logger.error('The service principal secret name is not given in live test.')
            raise ValueError()

        self.live = live
        self._storage = storage_secret_name
        self._sp = service_principal_secret_name

        super(AzureCliJob, self).__init__(name=name, image=image, parallelism=parallelism, run_id=run_id)

        self.labels['run_live'] = str(live)

    def create_volumes(self) -> Optional[Dict[str, V1Volume]]:
        """Return a mountPath -> volume map for customization. Otherwise returns None."""

        return {
            '/mnt/storage':
                V1Volume(name='azure-storage', azure_file=V1AzureFileVolumeSource(secret_name=self._storage,
                                                                                  share_name='k8slog'))
        }

    def create_environments(self) -> Optional[List[V1EnvVar]]:
        """Return environment variable settings. Otherwise return None."""
        if not self.live:
            return None

        return [
            V1EnvVar(name='A01_RUN_LIVE', value='True'),
            V1EnvVar(name='A01_SP_USERNAME',
                     value=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=self._sp, key='username'))),
            V1EnvVar(name='A01_SP_PASSWORD',
                     value=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=self._sp, key='password'))),
            V1EnvVar(name='A01_SP_TENANT',
                     value=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=self._sp, key='tenant')))]


class AzureCliMonitorJob(JobTemplate):
    def __init__(self, name: str, image: str, run_id: str, interval: int = 30, email: str = None,
                 official: bool = False) -> None:
        self.interval = interval
        self.email = email
        self.official = official

        super(AzureCliMonitorJob, self).__init__(name=name, image=image, parallelism=None, run_id=run_id)

        self.start_command = None

    def get_metadata(self) -> V1ObjectMeta:
        metadata = super(AzureCliMonitorJob, self).get_metadata()
        metadata.name = f'{self.name}-monitor'
        return metadata

    def create_volumes(self) -> Optional[Dict[str, V1Volume]]:
        """Return a mountPath -> volume map for customization. Otherwise returns None."""
        return None

    def create_environments(self) -> Optional[List[V1EnvVar]]:
        """Return environment variable settings. Otherwise return None."""
        envs = [
            V1EnvVar(name='A01_MONITOR_RUN_ID', value=self.run_id),
            V1EnvVar(name='A01_MONITOR_INTERVAL', value=str(self.interval))
        ]

        if self.email or self.official:
            secret = 'azurecli-email'
            envs.extend([
                V1EnvVar(name='A01_REPORT_SMTP_SERVER',
                         value=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=secret, key='server'))),
                V1EnvVar(name='A01_REPORT_SENDER_ADDRESS',
                         value=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=secret, key='username'))),
                V1EnvVar(name='A01_REPORT_SENDER_PASSWORD',
                         value=V1EnvVarSource(secret_key_ref=V1SecretKeySelector(name=secret, key='password')))])

            if self.official:
                envs.append(V1EnvVar(name='A01_REPORT_RECEIVER',
                                     value=V1EnvVarSource(
                                         config_map_key_ref=V1ConfigMapKeySelector(name='azurecli-config',
                                                                                   key='official.email'))))
            elif self.email:
                envs.append(V1EnvVar(name='', value=self.email))

        return envs
