import base64

import tabulate
from kubernetes import config as kube_config
from kubernetes import client as kube_client

from a01.cli import cmd, arg


@cmd('get secrets', desc='Show the secrets')
@arg('namespace', help='The namespace of the secrets. Default: a01-prod')
@arg('full', help='Display the full secrets.')
def show_secrets(namespace: str = 'a01-prod', full: bool = False):
    kube_config.load_kube_config()

    view = []
    for secret in kube_client.CoreV1Api().list_namespaced_secret(namespace).items:
        if secret.type in ('kubernetes.io/service-account-token', 'kubernetes.io/tls'):
            continue

        for key, value in secret.data.items():
            value = base64.b64decode(value).decode('utf-8')
            if not full and len(value) > 20:
                value = value[:20] + " ..."
            view.append([secret.metadata.name, secret.metadata.labels, key, value])

    print(tabulate.tabulate(view, tablefmt="plain"))
