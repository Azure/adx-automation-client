# How to onboard to a01 testing

## Docker container

A01 runs tests inside a container. The container should look like this:

- Test code sohuld be included in the container, of course, ready to run.

- Include a test list. As a small example, a two test list for the Go SDK looks like this:

``` json
[
  {
    "ver": "1.0",
    "execution": {
      "command": "go test -v github.com\\Azure-Samples\\azure-sdk-for-go-samples\\sql -run ^ExampleDatabaseQueries$"
    },
    "classifier": {
      "identifier": "sql/DatabaseQueries"
    }
  },
  {
    "ver": "1.0",
    "execution": {
      "command": "go test -v github.com\\Azure-Samples\\azure-sdk-for-go-samples\\storage -run ^ExampleUploadBlockBlob$"
    },
    "classifier": {
      "identifier": "storage/UploadBlockBlob"
    }
  }
]
```

This example is showing all the required fields. However, the test list might also contain other fields.

- Have an `app` folder with:
  - `get_index` program. This program should print the test list.
  - `a01droid` binary, you can get it in https://a01tools.blob.core.windows.net/droid/latest/linux/a01droid . Find more [info about the a01droid](https://github.com/Azure/adx-automation-agent).

The `app` folder might also have a `prepare_pod` and/or and `after_test` program.

- Have the following labels:

``` dockerfile
LABEL a01.product="<your-product-name>"
LABEL a01.index.schema="v2"
```

Other labels can be added, for example, if tests run with specific credentials set as environment variables:

``` dockerfile
LABEL a01.env.AZ_CLIENT_SECRET="secret:<your-secret-data-key-in-kubernetes>"
```

- And at the end, run the a01droid:

``` dockerfile
CMD app/droid
```

The container image should be pushed to our container registry before creating a run. This can be done as part of CI when checking in code to your product's repo, so tests can be run with all the newest changes.

In case you want to use a mount volume during the run, add this to the dockerfile. For example, the Azure CLI tests use this to store HTTP recordings, with the `after_test` program.

``` dockerfile
LABEL a01.setting.storage="True"
```

A01 client has a `--mode` flag, which can be used when creating runs (run `a01 create run -h` to get more info). Mode flag will set the value for an env var that can be included in the dockerfile.

``` dockerfile
LABEL a01.env.YOUR_ENV_VAR="arg-mode"
```

## Logs storage account

Create a storage account, tests' logs will be kept there. Create a file share called `k8slog`. Now, create a SAS URI for that fileshare. This can be done like this from the Azure CLI

``` bash
az storage share generate-sas-n k8slog --expiry <choose-an-expiry> --permissions r --account-key <your-storage-account-key> --account-name <your-storage-account-name>
```

The full SAS URI should look something like this:

```
https://mytests.file.core.windows.net/k8slog/{}?se=2019-10-31T00%3A00%3A00Z&sp=r&sv=2017-07-29&sr=s&sig=veryInterestingSignature
```

Notice the curly braces `{}` somewhere in the middle? They will be important later so logs are organized in directories.

## Kubernetes secrets

Add the [secrets](https://kubernetes.io/docs/concepts/configuration/secret/) your tests need to run to kubernetes. Required data in the secret are `azurestorageaccountkey`, `azurestorageaccountname` and `log.path.template` (this last one is the filse share SAS URI). The secret object should look similar to this:

```yaml
apiVersion: v1
data:
  azurestorageaccountkey: <base-64-encoded-account-key>
  azurestorageaccountname:  <base-64-encoded-account-name>
  log.path.template:  <base-64-encoded-SAS-URI>
  cred: <base-64-encoded-cred>
kind: Secret
metadata:
  name: <your-product-name>
type: Opaque
```

The kubernetes secret's name value, should be exactly the same as the value for the `a01.product` label in the dockerfile. The data keys that are not rquired (for example, the `cred` data key), should have the same key as whatever the `a01.env.VAR_NAME` label has as value in the dockerfile, minus the `secret:` prefix.