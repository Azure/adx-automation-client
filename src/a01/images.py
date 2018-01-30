import json
import shlex
from subprocess import check_output, CalledProcessError

import tabulate

import a01.cli
from a01.common import DROID_CONTAINER_REGISTRY, IS_WINDOWS, get_logger


@a01.cli.cmd('get images', desc='List the droid images')
@a01.cli.arg('author', help='The author of the droid image. The official image\' author is "azure" which is the '
                            'default value.')
@a01.cli.arg('latest', option=('-l', '--latest'), help='Return the latest droid image.')
def list_images(author: str = 'azure', latest: bool = False) -> None:
    try:
        author = f'private-{author}' if author != 'azure' else author
        repo = f'azurecli-test-{author}'
        output = check_output(shlex.split(f'az acr repository show-tags --repository {repo} '
                                          f'-n {DROID_CONTAINER_REGISTRY} -ojson', posix=not IS_WINDOWS),
                              shell=IS_WINDOWS)
        # assume all on same python version and platform
        image_list = [_DroidImage(f'{DROID_CONTAINER_REGISTRY}.azurecr.io', repo, tag) for tag in json.loads(output)]
        image_list = sorted(image_list, key=lambda img: img.build_number, reverse=True)

        if latest:
            print(image_list[0].__repr__())
        else:
            print(tabulate.tabulate([{'image': img.__repr__()} for img in image_list]))
    except CalledProcessError:
        get_logger(__name__).exception(f'Fail to list images for {repo}')


class _DroidImage(object):  # pylint: disable=too-few-public-methods
    def __init__(self, server: str, repository: str, tag: str) -> None:
        self._build_number = -1

        self.tag = tag
        self.full_name = f'{server}/{repository}:{tag}'
        self.python_version, self.build_number = tag.split('-')

    @property
    def build_number(self) -> int:
        return self._build_number

    @build_number.setter
    def build_number(self, value):
        self._build_number = int(value)

    def __repr__(self):
        return self.full_name
