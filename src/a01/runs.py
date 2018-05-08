from a01.common import get_logger, A01Config
from a01.cli import cmd, arg
from a01.communication import session

# pylint: disable=too-many-arguments, invalid-name

logger = get_logger(__name__)



@cmd('restart run', desc='Restart a run. This command is used when the Kubernetes Job behaves abnormally. It will '
                         'create new group of controller job and test job with the same settings.')
@arg('run_id', help='Then run to restart', positional=True)
def restart_run(run_id: str):
    config = A01Config()
    resp = session.post(f'{config.endpoint_uri}/run/{run_id}/restart')
    resp.raise_for_status()


@cmd('delete run', desc='Delete a run as well as the tasks associate with it.')
@arg('run_id', help='Ids of the run to be deleted.', positional=True)
def delete_run(run_id: str) -> None:
    config = A01Config()
    resp = session.delete(f'{config.endpoint_uri}/run/{run_id}')
    resp.raise_for_status()
