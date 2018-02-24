# A01 - The CLI for ADX Automation System

## Prerequisite

- Install [Python 3.6](https://www.python.org/downloads/)
- Install [Docker CE](https://www.docker.com/community-edition#/download)
- Install [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest)
- Run `az aks install-cli` to install Kubectl using Azure CLI 
- Run `az login` to login Azure using Azure CLI. Please use the corp account.

## Install

- The latest tagged version can be download here: https://a01tools.blob.core.windows.net/client/adx_automation_cli_latest.whl
- Note: 
    - Through virtual environment is not required, it is nevertheless included in following examples as a good practice.
    - The earlier version can be found at https://a01tools.blob.core.windows.net/client/archive/adx_automation_cli-{VERSION}-py3-none-any.whl

### Bash

```bash

$ virtualenv env --python=python3
$ . env/bin/activate
$ pip install https://a01tools.blob.core.windows.net/client/adx_automation_cli_latest.whl

```

### Windows

```cmd

> python -m virtualenv env --python=python3.6
> env\Scripts\activate
> pip install https://a01tools.blob.core.windows.net/client/adx_automation_cli_latest.whl

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
