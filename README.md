# A01 - The CLI for ADX Automation System

## Prerequisite

- Install [Python 3.6](https://www.python.org/downloads/)
- Install [Docker CE](https://www.docker.com/community-edition#/download)
- Install [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest)
- Run `az aks install-cli` to install Kubectl using Azure CLI 
- Run `az login` to login Azure using Azure CLI. Please use the corp account.
- Run `az account set -s 6b085460-5f21-477e-ba44-1035046e9101` to switch to the subscription containing the Kubernetes cluster. If you don't have access to the subscription, please ask for help.

## Install

- Find the latest [release](https://github.com/Azure/adx-automation-client/releases).
- Save the link to the wheel file as <PATH_TO_WHEEL>
- Note: in the following instruction, virtual environment is set up. It is not required but it is helpful to manage the dependencies.

### Bash

```bash

$ virtualenv env --python=python3
$ . env/bin/activate
$ pip install <PATH_TO_WHEEL>

```

### Windows

```cmd

> python -m virtualenv env --python=python3.6
> env\Scripts\activate
> pip install <PATH_TO_WHEEL>

```

## Initialize

- Run `a01 check` to validate environment.
- Run `a01 login --endpoint a01.azclitest.com` to login.

# Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
