import sys
import shlex
import json
from typing import Callable
from subprocess import check_output, CalledProcessError, STDOUT

import requests
import colorama

import a01.cli
from a01.common import KUBE_STORE_NAME


@a01.cli.cmd('check', desc='Examine the current settings and environment.')
def check_environment():
    result = True
    result &= verify_item('Azure CLI', 'az --version')
    result &= verify_item('Azure CLI login', 'az account show')
    result &= verify_item('Kubernete CLI', 'kubectl version', 'Install kubectl using "az aks install-cli" command.')
    result &= verify_item('Kubernete namespace az', 'kubectl get namespace az',
                          'The cluster must have a namespace named az associated. You may not have log in your '
                          'kubectrl with correct AKS service. Run "az aks get-credentials -n <aks_service>" to login.')

    cmd = f'kubectl get service {KUBE_STORE_NAME} --namespace az' + ' -ojsonpath={.status.loadBalancer.ingress[0].ip}'
    result &= verify_item('Kubernete service', cmd,
                          'There must be service named "task-store-web-service" exposed in the az namespace.',
                          check_task_store_healthy)

    sys.exit(0 if result else 1)


def verify_item(name: str, command: str, hint: str = None, validate_fn: Callable[[str], None] = lambda _: None) -> bool:
    try:
        sys.stderr.write(f'Validating {name} ... ')
        sys.stderr.flush()
        output = check_output(shlex.split(command), stderr=STDOUT).decode('utf-8')
        validate_fn(output)

        sys.stderr.write(colorama.Fore.GREEN + 'ok\n' + colorama.Fore.RESET)
        sys.stderr.flush()

        return True

    except (CalledProcessError, ValueError, requests.HTTPError):
        sys.stderr.write(colorama.Fore.RED + 'failed\n' + colorama.Fore.RESET)
        if hint:
            sys.stderr.write(colorama.Fore.YELLOW + hint + '\n' + colorama.Fore.RESET)

        sys.stderr.flush()
        return False


def check_task_store_healthy(ip: str) -> None:
    resp = requests.get(f'http://{ip}/healthy')
    resp.raise_for_status()
    if json.loads(resp.content.decode('utf-8'))['status'] != 'healthy':
        raise ValueError()
