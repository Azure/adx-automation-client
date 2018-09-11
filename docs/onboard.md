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
  - `metadata.yml` file. This file will include settings for your runs.

The `app` folder might also have a `prepare_pod` and/or and `after_test` program.

At the end, run a01droid. You can learm more about a01droid [here](https://github.com/Azure/adx-automation-agent).

``` dockerfile
CMD /mnt/agents/a01droid
```

The container image should be pushed to our container registry before creating a run. This can be done as part of CI when checking in code to your product's repo, so tests can be run with all the newest changes.

## Metadata YAML file

A file for adding setting to your test runs. It should have this properties:

``` yaml
kind: DroidMetadata
version: v3
product: <your-product-name>
storage: true
```

More settings can be added, for example, if tests run with specific credentials set as environment variables:

``` yaml
environments:
  - name: <your-environment-variable-name>
    type: secret
    value: <your-secret-data-key-in-kubernetes>
```

To inject credentials as files, add this:

``` yaml
secretFiles:
  - path: <your-relative-file-path>
    secretKey: <your-secret-data-key-in-kubernetes>
```

Your file content should be added to your product's Kubernetes secret. Secret files will be placed in `/mnt/secrets` volume.

A01 client has a `--mode` flag, which can be used when creating runs (run `a01 create run -h` to get more info). Mode flag will set the value for an env var that can be included in the metadata file.

``` yaml
environments:
  - name: <your-environment-variable-name>
    type: argument-value-mode
```

## Logs storage account

Create a storage account, tests' logs will be kept there. Create a file share called `k8slog`. Now, create a SAS URI for that fileshare. This can be done like this from the Azure CLI

``` bash
az storage share generate-sas-n k8slog --expiry <choose-an-expiry> --permissions r --account-key <your-storage-account-key> --account-name <your-storage-account-name>
```

The full SAS URI should look something like this:

``` url
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

The kubernetes secret's name value, should be exactly the same as the value for the `product` label in the `metadata.yml` file. The data keys that are not rquired (for example, the `cred` data key), should have the same name as they have in the `metadata.yml` file.

## Emails (optional)

### Recipients

Receive notification emails after tests runs have finished. Use the `--remark official` flag when creating runs to send emails to your team. The recipient list should be set in your product's Kubernetes secret, with key `owners`.
A01 can also send emails with weekly summaries (Mondays at 7AM). Set the recipients list on the product's Kubernetes secret, with key `owners.weekly`.

### Customize

A01 can send generic emails, but you might want to customize the email for your product. First, create a [Jinja2](http://jinja.pocoo.org/docs/2.10/) template. Upload it to a storage account (you can use the same storage account used for logs), and get its SAS URI. Provide the SAS URI in your product's Kubernetes secret, with key `email.path.template`, or `email.path.template.weekly`. Good examples are the [generic email template](https://github.com/Azure/adx-automation-services/blob/master/services/email/app/app/templates/generic.html), and the [generic weekly email template](https://github.com/Azure/adx-automation-services/blob/master/services/newsletter/app/templates/generic.html).


```yaml
apiVersion: v1
data:
  owners: <comma-separated-emails>
  owners.weekly: <comma-separated-emails>
  email.path.template: <SAS-URI-to-jinja2-template>
  email.path.template.weekly: <SAS-URI-to-jinja2-template>
kind: Secret
metadata:
  name: <your-product-name>
type: Opaque
```

## PowerBI reports (optional)

A01 has support for PowerBI reports displaying test run results. It can refresh a dataset once the test run has finished.

### Create and share your PowerBI report

The report's data source is a PostgreSQL database (you will need the database creds to create the report). After you have finished your report, publish it to your team's workspace. The same user that is setup to send emails on test runs, should be added to the PBI workspace. Login as that user to the PowerBI portal, and make it take ownership on the dataset previously shared on the workspace. Setup an on-premises data gateway ([documentation here](https://powerbi.microsoft.com/en-us/gateway/)) that connects to the PostgreSQL database and provide it with the database credentials. The gateway is required to be able to refresh data.

### Refresh your dataset on every test run

A01 needs PowerBI credentials to refresh datasets, and they should set on the `email` kubernetes secret.

```yaml
apiVersion: v1
data:
  username: <email-acount>
  password:  <email-password>
  powerbi.client.id:  <PowerBI-client-ID>
kind: Secret
metadata:
  name: email
type: Opaque
```

To get a client ID, [register an app on Azure AD](https://docs.microsoft.com/en-us/power-bi/developer/walkthrough-push-data-register-app-with-azure-ad). The app should be set to `Native app`, and should have the `Read And Write All Datasets` permission.

Required parameters to refresh a dataset are its `groupID` and `datasetID`. Add this values to your product's Kuberenetes secret:

```yaml
apiVersion: v1
data:
  powerbi.dataset: <PowerBI-dataset>
  powerbi.group: <PowerBI-group>
kind: Secret
metadata:
  name: <your-product-name>
type: Opaque
```

A little note on PowerBI refreshes: depending on your workspace capacity, it might be [limit to 8 refreshes per day](https://powerbi.microsoft.com/en-us/blog/announcing-data-refresh-apis-in-the-power-bi-service/). A01 is set up to only refresh datasets on runs started with the `--remark official` flag.