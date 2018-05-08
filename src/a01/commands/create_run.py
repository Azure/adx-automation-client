import sys
import logging

import a01
from a01.models import Run
from a01.cli import arg, cmd
from a01.auth import AuthSettings


@cmd('create run', desc='Create a new run.')
@arg('image', help='The droid image to run.', positional=True)
@arg('parallelism', option=('-p', '--parallelism'),
     help='The number of job to run in parallel. Can be scaled later through kubectl.')
@arg('from_failures', option=['--from-failures'], help='Create the run base on the failed tasks of another run')
@arg('live', help='Run test live')
@arg('mode', help='The mode in which the test is run. The option accept a string which will be passed on to the pod as '
                  'an environment variable. The meaning of the string is open for interpretations.')
@arg('query', help='The regular expression used to query the tests.')
@arg('exclude', help='The regular expression used to exclude tests.')
@arg('remark', help='The addition information regarding to this run. Specify "official" will trigger an email '
                    'notification to the entire team after the job finishes.')
@arg('email', help='Send an email to you after the job finishes.')
@arg('secret', help='The name of the secret to be used. Default to the image\'s a01.product label.')
@arg('agent', help='The version of the agent to be used. Default to latest.')
# pylint: disable=too-many-arguments, too-many-locals
def create_run(image: str, from_failures: str = None, live: bool = False, parallelism: int = 3, query: str = None,
               remark: str = '', email: bool = False, secret: str = None, mode: str = None, exclude: str = None,
               agent: str = 'latest') -> None:
    auth = AuthSettings()
    remark = remark or ''
    creator = auth.get_user_name()
    agent = agent.replace('.', '-')

    reg, image_name = image.split('/', 1)
    reg = reg.split('.')[0]

    try:
        run_model = Run(name=f'Run of {image_name} from {reg}',
                        settings={
                            'a01.reserved.imagename': image,
                            'a01.reserved.imagepullsecret': 'azureclidev-registry',
                            'a01.reserved.secret': secret,
                            'a01.reserved.storageshare': 'k8slog',
                            'a01.reserved.testquery': query,
                            'a01.reserved.testexcludequery': exclude,
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

        sys.exit(0)
    except ValueError as ex:
        logger = logging.getLogger(__name__)
        logger.error(ex)
        sys.exit(1)
