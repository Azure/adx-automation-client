# The command line tool for the A01 system

## Prerequisite

- Python 3.6+
- Run `a01 check` to validate environment.

- Docker CE
- Azure CLI
- Kubectl

## Install

### Bash

```bash

$ virtualenv env --python=python3
$ . env/bin/activate
$ curl -sOL https://github.com/troydai/a01client/releases/download/0.3.2/a01ctl-0.3.2-py3-none-any.whl
$ pip install a01ctl-0.3.2-py3-none-any.whl

```

### Windows

- Download the file https://github.com/troydai/a01client/releases/download/0.3.2/a01ctl-0.3.2-py3-none-any.whl (or the latest release)

```cmd

> python -m virtualenv env --python=python3.6
> env\Scripts\activate
> pip install <PATH_TO_WHEEL>

```
