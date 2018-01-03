#!/usr/bin/env python3

import logging
import yaml
import os
import base64
import tempfile
import shlex
import argparse
import requests
from subprocess import check_call, check_output


parser = argparse.ArgumentParser()
parser.add_argument('run_id', help='The run this job to run against.')
parser.add_argument('-p', dest='parallelism', help='The parallelism. Default: 3', default=3, type=int)
parser.add_argument('--store', help='The a01 store name. Default: a01store', default='a01store')
parser.add_argument('--live', help='Run test live.', action='store_true')
parser.add_argument('--secret', help='The kubernetes secret providing service principal. Default: azurecli-live-sp',
                    default='azurecli-live-sp')
parser.add_argument('--storage', help='The kubernetes secret providing Azure Storage Account credential for logging', 
                    default='azurecli-test-storage')
args = parser.parse_args()


store_ip = check_output(
    'kubectl get service a01store -ojsonpath={.status.loadBalancer.ingress[0].ip}'.split(' ')).decode('utf-8')
store_uri = f'http://{store_ip}'

run_details = requests.get(f'{store_uri}/run/{args.run_id}').json()
image = run_details['settings']['droid_image']

job_name = f'azurecli-test-{base64.b32encode(os.urandom(12)).decode("utf-8").lower()}'.rstrip('=')

job_config = {
    'apiVersion': 'batch/v1',
    'kind': 'Job',
    'metadata': {
        'name': job_name
    },
    'spec': {
        'parallelism': args.parallelism,
        'backoffLimit': 5,
        'template': {
            'metadata': {
                'name': job_name
            },
            'spec': {
                'containers': [{
                    'name': 'droid',
                    'image': image,
                    'command': ['python', '/app/job.py'],
                    'volumeMounts': [
                        {'name': 'azure-storage', 'mountPath': '/mnt/storage'}
                    ],
                    'env': [
                        {'name': 'ENV_POD_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'metadata.name'}}},
                        {'name': 'ENV_NODE_NAME', 'valueFrom': {'fieldRef': {'fieldPath': 'spec.nodeName'}}},
                        {'name': 'A01_DROID_RUN_ID', 'value': args.run_id}
                    ]
                }],
                'restartPolicy': 'Never',
                'volumes': [{
                    'name': 'azure-storage',
                    'azureFile': {
                        'secretName': args.storage,
                        'shareName': 'k8slog',
                    }}]
            }
        }
    }
}

if args.live:
    envs = job_config['spec']['template']['spec']['containers'][0]['env']
    envs.append({'name': 'A01_RUN_LIVE', 'value': 'True'})
    envs.append(
        {'name': 'A01_SP_USERNAME', 'valueFrom': {'secretKeyRef': {'name': 'azurecli-live-sp', 'key': 'username'}}})
    envs.append(
        {'name': 'A01_SP_PASSWORD', 'valueFrom': {'secretKeyRef': {'name': 'azurecli-live-sp', 'key': 'password'}}})
    envs.append({'name': 'A01_SP_TENANT', 'valueFrom': {'secretKeyRef': {'name': 'azurecli-live-sp', 'key': 'tenant'}}})

_, name = tempfile.mkstemp(text=True)
with open(name, 'w') as f:
    yaml.dump(job_config, f, default_flow_style=False)

print(f'Temp config file created at {name}')
check_call(shlex.split(f'kubectl create -f {name}'))
