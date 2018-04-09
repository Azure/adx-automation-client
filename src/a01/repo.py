import sys
import base64

import yaml
import docker
import docker.errors
import requests
import colorama
from kubernetes import config as kube_config
from kubernetes import client as kube_client
from tabulate import tabulate

from a01.models import Task, Run
from a01.cli import cmd, arg

# pylint: disable=too-many-statements


@cmd('repo task', desc="Rerun a task locally")
@arg('task_id', positional=True)
@arg('live', help='Rerun in live env')
@arg('interactive', option=['-i', '--interactive'], help='Start the container in interactive mode')
@arg('shell', help='The shell to use for interactive mode')
@arg('mode', help='Need a mode')
def reproduce_task(task_id: str, live: bool = False, interactive: bool = False, shell: str = '/bin/bash',
                   mode: str = None) -> None:
    task = Task.get(task_id)
    run = Run.get(task.run_id)

    summary = {
        'name': task.name,
        'image': run.image,
        'command': task.command,
    }

    print('\nBrief\n')
    print(tabulate(summary.items(), tablefmt='plain'))
    print()

    try:
        client = docker.from_env()

        if not client.images.list(run.image):
            print('Pulling the test image ...')
            client.images.pull(*(run.image.split(':')))
        else:
            print(f'Image {run.image} exists locally.')

        print('Retrieve metadata')
        metadata = client.containers.run(run.image, 'cat /app/metadata.yml', remove=True)
        metadata = yaml.load(metadata)

        print('Get secrets from the Kubernetes cluster')
        kube_config.load_kube_config()
        kapi = kube_client.CoreV1Api()

        secret = kapi.read_namespaced_secret(run.product, 'a01-prod')
        repo_environment_variables = {}

        for env in metadata['environments']:
            if env['type'] == 'secret':
                value = secret.data[env['value']]
                value = base64.b64decode(value).decode('utf-8')

                repo_environment_variables[env["name"]] = value
            elif env['type'] == 'argument-switch-live':
                if live:
                    repo_environment_variables[env["name"]] = env["value"]
            elif env['type'] == 'argument-value-mode':
                if mode:
                    repo_environment_variables[env['name']] = mode

        print('Environment:')
        print(tabulate(repo_environment_variables.items(), tablefmt='plain') + '\n')

        if interactive:
            print('Start the container in interactive mode ...\n')
            cont = client.containers.run(run.image, shell, environment=repo_environment_variables, auto_remove=True,
                                         detach=True, tty=True, stdin_open=True)
            print(f'\n\nRun following command to enter the container\'s shell:')
            print(f'\n{colorama.Fore.YELLOW}docker attach {cont.name}{colorama.Fore.RESET}\n')
            print(f'\nRun following command in the container to rerun the task:')
            print(f'\n{colorama.Fore.YELLOW}{task.command}{colorama.Fore.RESET}\n\n')

        else:
            print('Run task in local container ...\n')

            command = f'/bin/bash -c "if [ -e /app/prepare_pod ]; then /app/prepare_pod; fi; {task.command}"'
            cont = client.containers.run(run.image, command, environment=repo_environment_variables, detach=True)
            cont.wait()
            print('\nRun finished ...\n')

            print(colorama.Fore.LIGHTYELLOW_EX + cont.logs().decode('utf-8') + colorama.Fore.RESET)
            cont.remove()

    except requests.HTTPError:
        print(f'Please login the docker container registry {run.image.split("/")[0]}')
        sys.exit(1)
