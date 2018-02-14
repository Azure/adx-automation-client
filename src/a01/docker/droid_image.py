import functools
import json
import re
from typing import List

import docker
import docker.errors
import docker.models.images

from a01.common import get_logger


class DroidImage(object):
    def __init__(self, image_name: str) -> None:
        self.logger = get_logger(DroidImage.__class__.__name__)

        self.image_name = image_name
        try:
            self.repo, self.tag = image_name.rsplit(':', 1)
        except ValueError:
            raise ValueError('Incorrect image name. The tag is missing.')

        self.client = docker.from_env()
        self._image = None

    @functools.lru_cache(maxsize=4)
    def list_tasks(self, query: str = None) -> List[dict]:
        image_labels = self.image.labels
        index_schema_version = image_labels.get('a01.index.schema', 'v1')

        tests = self._get_test_index(index_schema_version)

        if query:
            tests = [t for t in tests if re.match(query, t['path'])]

        return tests

    @property
    def product_name(self) -> str:
        return self.image.labels.get('a01.product', None)

    @property
    def secret_to_env(self) -> dict:
        """The secret key to environment variable map. The secret name is decided by the image label a01.product or
        what the user specifies."""
        result = {}
        for key, value in self.image.labels.items():
            if key.startswith('a01.env.') and value.startswith('secret:'):
                result[key[8:]] = value[7:]
        return result

    @property
    def live_env(self) -> (str, str):
        for key, value in self.image.labels.items():
            if key.startswith('a01.env.') and value.startswith('arg-live:'):
                return key[8:], value[9:]
        return None, None

    @property
    def mount_storage(self) -> bool:
        return self.image.labels.get('a01.setting.storage', 'True') == 'True'

    @property
    def image(self) -> docker.models.images.Image:
        try:
            if not self._image:
                # try to list the image locally first
                images = self.client.images.list(name=self.image_name)
                if images:
                    self._image = images[0]
                else:
                    self._image = self.client.images.pull(self.image_name)

            return self._image
        except docker.errors.NotFound:
            self.logger.debug(f'Not found {self.image_name}', exc_info=True)
            raise ValueError(f'Image not found {self.image_name}')
        except docker.errors.APIError:
            self.logger.debug(f'Fail to pull image {self.image_name}', exc_info=True)
            raise ValueError(f'Fail to pull image {self.image_name}')

    def _get_test_index(self, schema_version: str) -> List[dict]:
        try:
            if schema_version == 'v1':
                output = self.client.containers.run(image=self.image_name, command=['python', '/app/collect_tests.py'],
                                                    remove=True)
            elif schema_version == 'v2':
                output = self.client.containers.run(image=self.image_name, command=['/app/get_index'], remove=True)
            else:
                raise ValueError(f'Unknown schema {schema_version}.')

            return json.loads(output)
        except docker.errors.ContainerError:
            self.logger.debug('Docker container error.', exc_info=True)
            raise ValueError('Fail to execute the list tests script in the container.')
        except docker.errors.APIError:
            self.logger.debug('Docker operation failed.', exc_info=True)
            raise ValueError('Fail to execute the list tests script in the container.')
        except (json.JSONDecodeError, TypeError):
            self.logger.debug('JSON parsing error.', exc_info=True)
            raise ValueError('Fail to parse the output into JSON.')
