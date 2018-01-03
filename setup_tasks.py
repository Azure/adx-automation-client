#!/usr/bin/env python3

import sys
import json
import os
import base64
import argparse
from subprocess import check_output, CalledProcessError

import tabulate
import requests


def get_cache_dir(image_name):
    try:
        image_details = json.loads(check_output(['docker', 'image', 'inspect', image_name]))
        image_id = image_details[0]['Id'].split(':')[1]
        cache_dir = os.path.join(os.getcwd(), '.cache', image_id)
        if not os.path.isdir(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    except (CalledProcessError, json.JSONDecodeError, TypeError, IOError):
        pass


def get_store_uri():
    # Get the public IP of the store service using kubectl, you need to authenticate yourself first.
    store_ip = check_output(
        'kubectl get service a01store -ojsonpath={.status.loadBalancer.ingress[0].ip}'.split(' ')).decode('utf-8')
    return f'http://{store_ip}'


def get_manifest(image_name, from_failures):
    if from_failures:
        all_tasks = requests.get(f'{get_store_uri()}/run/{from_failures}/tasks').json()
        failed_test_paths = set([task['settings']['path'] for task in all_tasks if task['result'] != 'Passed'])
    else:
        failed_test_paths = None

    try:
        manifest_file = os.path.join(get_cache_dir(image_name), 'manifest.json')
        with open(manifest_file, mode='r') as mf:
            manifest = json.load(mf)
    except (json.JSONDecodeError, TypeError, IOError):
        try:
            container_name = base64.b32encode(os.urandom(12))[:-4]
            manifest = json.loads(
                check_output(['docker', 'run', '--name', container_name, image_name, 'python', '/app/collect_tests.py']))
        except CalledProcessError:
            print(f'Failed to list tests in image {image_name}.', file=sys.stderr)
            sys.exit(1)
        except (json.JSONDecodeError, TypeError) as error:
            print('Failed to parse the manifest as JSON.', file=sys.stderr)
            print(error, file=sys.stderr)
            sys.exit(1)

        try:
            check_output(['docker', 'rm', container_name])
        except CalledProcessError:
            print(f'Failed to remove container {container_name}.', file=sys.stderr)
            sys.exit(1)

        with open(os.path.join(get_cache_dir(image_name), 'manifest.json'), mode='w') as wmf:
            json.dump(manifest, wmf)

    if failed_test_paths:
        manifest = [each for each in manifest if each['path'] in failed_test_paths]
    return manifest


def schedule_tests(manifest, image_name):
    print(f'{len(manifest)} tests to run.')
    store_uri = get_store_uri()

    print(requests.get(f'{store_uri}/runs').json())

    # create a run
    resp = requests.post(f'{store_uri}/run', json={
        'name': f'Azure CLI Test with {image_name}',
        'settings': {
            'droid_image': image_name
        },
        'details': {
            'creator': 'Troy Dai (troy.dai@outlook.com)',
            'purpose': 'demo'
        }
    })
    resp.raise_for_status()
    run_id = resp.json()['id']

    # create tasks
    task_payload = [
        {
            'name': f'Test: {each["path"]}',
            'annotation': image_name,
            'settings': {
                'path': each['path'],
            }
        } for each in manifest]
    requests.post(f'{store_uri}/run/{run_id}/tasks', json=task_payload).raise_for_status()
    print(f'created run {run_id}')


def main(arguments):
    manifest = get_manifest(arguments.image, arguments.from_failures)
    if arguments.module_prefix:
        manifest = [m for m in manifest if m['module'].startswith(arguments.module_prefix)]

    if args.list:
        print(tabulate.tabulate([(m['module'], m['class'], m['method']) for m in manifest],
                                headers=('module', 'class', 'method')))
    else:
        schedule_tests(manifest, arguments.image)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create new run and tasks')
    parser.add_argument('image', help='The Azure CLI droid container image.')
    parser.add_argument('--list', help='Listing the tasks instead of adding them', action='store_true')
    parser.add_argument('--module-prefix', help='Limit the tasks to the specific module prefix.')
    parser.add_argument('--from-failures', help='Give a run id. Create a new run from the failed tasks of it.')
    args = parser.parse_args()
    main(args)
