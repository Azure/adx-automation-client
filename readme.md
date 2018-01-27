# The command line tool for the A01 system

## Prerequisite

- Python 3.6
- Install Kubectl and login to the cluster of your A01 system.
- Install az to login to the Azure Container Registry for droid image.
- Install docker to list images (optional).

## Install

### Bash

```bash

$ virtualenv env --python=python3
$ . env/bin/activate
$ curl -sOL https://github.com/troydai/a01client/releases/download/0.2.2/a01ctl-0.2.3-py3-none-any.whl
$ pip install a01ctl-0.2.3-py3-none-any.whl

```
