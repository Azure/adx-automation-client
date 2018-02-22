# The command line tool for the A01 system

## Prerequisite

- Install [Python 3.6](https://www.python.org/downloads/)
- Install [Docker CE](https://www.docker.com/community-edition#/download)
- Install [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli?view=azure-cli-latest)
- Install Kubectl using Azure CLI `az aks install-cli`
- Login Azure using Azure CLI with your Microsoft Account `az login`
- Switch to subscription 6b085460-5f21-477e-ba44-1035046e9101 `az account set -s 6b085460-5f21-477e-ba44-1035046e9101`

## Install

- Find the latest [release](https://github.com/troydai/a01client/releases).
- Save the link to the wheel file as <PATH_TO_WHEEL>

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
