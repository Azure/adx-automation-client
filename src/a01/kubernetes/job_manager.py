from kubernetes import client, config


class JobManager(object):
    """Manage the A01 job in the Kubernetes cluster"""

    def __init__(self):
        config.load_incluster_config()
        self.api = client.CoreV1Api()

        client.BatchApi()
