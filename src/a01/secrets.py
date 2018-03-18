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
    for s in kube_client.CoreV1Api().list_namespaced_secret(namespace).items:
        if s.type in ('kubernetes.io/service-account-token', 'kubernetes.io/tls'):
            continue

        for k, v in s.data.items():
            v = base64.b64decode(v).decode('utf-8')
            if not full and len(v) > 20:
                v = v[:20] + " ..."
            view.append([s.metadata.name, s.metadata.labels, k, v])

    print(tabulate.tabulate(view, tablefmt="plain"))
