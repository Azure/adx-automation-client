import json
import sys
from itertools import zip_longest

import colorama

import a01
import a01.models
from a01.common import get_logger, A01Config
from a01.cli import cmd, arg
from a01.communication import session
from a01.auth import AuthSettings, AuthenticationError
from a01.output import output_in_table
from a01.kube import create_controller_job, clean_up_jobs

# pylint: disable=too-many-arguments, invalid-name

logger = get_logger(__name__)


@cmd('get runs', desc='Retrieve the runs.')
@arg('owner', help='Query runs by owner.')
@arg('me', help='Query runs created by me.')
@arg('last', help='Returns the last NUMBER of records. Default: 20.')
@arg('skip', help='Returns the records after skipping given number of records at the bottom. Default: 0.')
def get_runs(me: bool = False, last: int = 20, skip: int = 0,
             owner: str = None) -> None:  # pylint: disable=invalid-name
    try:
        if me and owner:
            raise ValueError('--me and --user are mutually exclusive.')
        elif me:
            owner = AuthSettings().get_user_name()

        runs = a01.models.RunCollection.get(owner=owner, last=last, skip=skip)
        output_in_table(runs.get_table_view(), headers=runs.get_table_header())
    except ValueError as err:
        logger.error(err)
        sys.exit(1)
    except AuthenticationError as err:
        logger.error(err)
        print('You need to login. Usage: a01 login.', file=sys.stderr)
        sys.exit(1)


@cmd('get run', desc='Retrieve a run')
@arg('run_id', help='The run id.', positional=True)
@arg('log', help="Include the failed tasks' logs.", option=('-l', '--log'))
@arg('recording', option=('-r', '--recording'),
     help='Download the recording files in recording directory at current working directory. The recordings '
          'are flatten with the full test path as the file name if --az-mode is not specified. If --az-mode is '
          'set, the recording files are arranged in directory structure mimic Azure CLI source code.')
@arg('show_all', option=['--show-all'], help='Show all the tasks results.')
@arg('recording_az_mode', option=['--az-mode'],
     help='When download the recording files the files are arranged in directory structure mimic Azure CLI '
          'source code.')
@arg('raw', help='For debug.')
def get_run(run_id: str, log: bool = False, recording: bool = False, recording_az_mode: bool = False,
            show_all: bool = False, raw: bool = False) -> None:
    try:
        tasks = a01.models.TaskCollection.get(run_id=run_id)
        output_in_table(tasks.get_table_view(failed=not show_all), headers=tasks.get_table_header())
        output_in_table(tasks.get_summary(), tablefmt='plain')

        log_path_template = None
        if log or recording:
            run = a01.models.Run.get(run_id=run_id)
            log_path_template = run.get_log_path_template()

        if log:
            for failure in tasks.get_failed_tasks():
                output_in_table(zip_longest(failure.get_table_header(), failure.get_table_view()), tablefmt='plain')
                output_in_table(failure.get_log_content(log_path_template), tablefmt='plain',
                                foreground_color=colorama.Fore.CYAN)

            output_in_table(tasks.get_summary(), tablefmt='plain')

        if recording:
            print()
            print('Download recordings ...')
            for task in tasks.tasks:
                task.download_recording(log_path_template, recording_az_mode)

        if raw:
            run = a01.models.Run.get(run_id=run_id)
            print(json.dumps(run.to_dict(), indent=2))
    except ValueError as err:
        logger.error(err)
        sys.exit(1)


@cmd('create run', desc='Create a new run.')
@arg('image', help='The droid image to run.', positional=True)
@arg('parallelism', option=('-p', '--parallelism'),
     help='The number of job to run in parallel. Can be scaled later through kubectl.')
@arg('from_failures', option=['--from-failures'], help='Create the run base on the failed tasks of another run')
@arg('live', help='Run test live')
@arg('mode', help='The mode in which the test is run. The option accept a string which will be passed on to the pod as '
                  'an environment variable. The meaning of the string is open for interpretations.')
@arg('query', help='The regular expression used to query the tests.')
@arg('remark', help='The addition information regarding to this run. Specify "official" will trigger an email '
                    'notification to the entire team after the job finishes.')
@arg('email', help='Send an email to you after the job finishes.')
@arg('secret', help='The name of the secret to be used. Default to the image\'s a01.product label.')
@arg('agent', help='The version of the agent to be used. Default to latest.')
# pylint: disable=too-many-arguments, too-many-locals
def create_run(image: str, from_failures: str = None, live: bool = False, parallelism: int = 3, query: str = None,
               remark: str = '', email: bool = False, secret: str = None, mode: str = None,
               agent: str = 'latest') -> None:
    auth = AuthSettings()
    remark = remark or ''
    creator = auth.get_user_name()
    agent = agent.replace('.', '-')

    try:
        run_model = a01.models.Run(name=f'Azure CLI Test @ {image}',
                                   settings={
                                       'a01.reserved.imagename': image,
                                       'a01.reserved.imagepullsecret': 'azureclidev-registry',
                                       'a01.reserved.secret': secret,
                                       'a01.reserved.storageshare': 'k8slog',
                                       'a01.reserved.testquery': query,
                                       'a01.reserved.remark': remark,
                                       'a01.reserved.useremail': auth.user_id if email else '',
                                       'a01.reserved.initparallelism': parallelism,
                                       'a01.reserved.livemode': str(live),
                                       'a01.reserved.testmode': mode,
                                       'a01.reserved.fromrunfailure': from_failures,
                                       'a01.reserved.agentver': agent,
                                   },
                                   details={
                                       'a01.reserved.creator': creator,
                                       'a01.reserved.client': f'CLI {a01.__version__}'
                                   },
                                   owner=creator,
                                   status='Initialized')

        run = run_model.post()
        print(f'Published run {run.id}')

        create_controller_job(run)
        sys.exit(0)
    except ValueError as ex:
        logger.error(ex)
        sys.exit(1)


@cmd('restart run', desc='Restart a run. This command is used when the Kubernetes Job behaves abnormally. It will '
                         'create new group of controller job and test job with the same settings.')
@arg('run_id', help='Then run to restart', positional=True)
def restart_run(run_id: str):
    run = a01.models.Run.get(run_id)

    clean_up_jobs(run)
    create_controller_job(run)


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
def delete_run(run_id: str) -> None:
    config = A01Config()
    run = a01.models.Run.get(run_id)
    clean_up_jobs(run)
    resp = session.delete(f'{config.endpoint_uri}/run/{run_id}')
    resp.raise_for_status()
