#!/usr/bin/env python3

import sys
import curses
import time
import datetime
import requests
import tabulate
from collections import defaultdict
from subprocess import check_output

run_id = sys.argv[1]

store_ip = check_output(
    'kubectl get service task-store-web-service -ojsonpath={.status.loadBalancer.ingress[0].ip}'.split(' ')).decode('utf-8')
store_uri = f'http://{store_ip}'


def main(stdscr):
    while True:
        resp = requests.get(f'{store_uri}/run/{run_id}/tasks')
        resp.raise_for_status()
        tasks = resp.json()

        statuses = defaultdict(lambda: 0)
        results = defaultdict(lambda: 0)

        failure = []

        for task in tasks:
            status = task['status']
            result = task['result']

            statuses[status] = statuses[status] + 1
            results[result] = results[result] + 1

            if result == 'Failed':
                failure.append(
                    (task['id'],
                     task['name'].rsplit('.')[-1],
                     task['status'],
                     task['result'],
                     (task.get('result_details') or dict()).get('agent'),
                     (task.get('result_details') or dict()).get('duration')))

        status_summary = 'Task status: ' + ' | '.join(
            [f'{status_name}: {count}' for status_name, count in statuses.items()])

        result_summary = 'Results: ' + ' | '.join(
            [f'{result or "Not run"}: {count}' for result, count in results.items()])

        stdscr.addstr(0, 0, f'Update on {datetime.datetime.now()}. (refresh every 5 seconds)')
        stdscr.addstr(2, 0, status_summary)
        stdscr.addstr(3, 0, result_summary)
        stdscr.addstr(6, 0, 'Failed tasks')
        stdscr.addstr(7, 0,
                      tabulate.tabulate(failure, headers=('id', 'name', 'status', 'result', 'agent', 'duration(ms)')))

        stdscr.refresh()
        time.sleep(5)


try:
    curses.wrapper(main)
except KeyboardInterrupt:
    print('Bye.')
