import sys
import logging
import yaml
import requests
from subprocess import check_output, CalledProcessError

logging.basicConfig(level=logging.DEBUG)

try:
    run_id = sys.argv[1]
except IndexError:
    print(f'Usage: {sys.argv[0]} <Run ID>', file=sys.stderr)
    sys.exit(1)

try:
    with open('config.yaml') as fq:
        config = yaml.load(fq)
    store_name = config['store']
    store_ip = check_output(
        'kubectl get service a01store -ojsonpath={.status.loadBalancer.ingress[0].ip}'.split(' ')).decode('utf-8')
    store_uri = f'http://{store_ip}'
except IOError:
    print('Missing config.yaml', file=sys.stderr)
    sys.exit(1)
except KeyError as error:
    print(f'Incorrect config.yaml file: {error}', file=sys.stderr)
    sys.exit(1)
except CalledProcessError:
    print('Fail to run kubectl')


requests.delete(f'{store_uri}/run/{run_id}')
