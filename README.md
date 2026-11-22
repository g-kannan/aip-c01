# AIP-C01 hands-on practice

## Project 1: Amazon Bedrock Converse

A Python script and Streamlit playground to try text prompts and inspect model responses, token
usage, service-reported latency, and the stop reason. This is a manual experiment,
not an automated answer-quality benchmark.

### Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Python
3.10 or newer, and the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
Clone this repository, open a terminal in its root directory, and install dependencies:

```powershell
uv sync
```

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. uv manages
the local `.venv` automatically; you do not need to activate it before running.

Both interfaces use an AWS CLI profile through a Boto3 session. Configure a named
profile using your organization's credential method, such as
[`aws configure sso`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)
or `aws configure`. Create a text file named `.env` in the repository root (beside
`app.py`) with the following values, replacing them with your own profile, region,
and accessible model or inference profile as needed:

```dotenv
AWS_PROFILE=your-profile
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=apac.amazon.nova-micro-v1:0
```

No access keys, secret keys, or session tokens need to be copied into this
project. Credentials are resolved by the named profile in your existing AWS
configuration. The `.env` file remains ignored by Git.

To verify the profile from PowerShell:

```powershell
aws sts get-caller-identity --profile your-profile
```

If this is an IAM Identity Center (SSO) profile, renew an expired session with
`aws sso login --profile your-profile`. If it uses `aws login`, use
`aws login --profile your-profile`. The `boto3[crt]` dependency needed for these login
sessions is included in `pyproject.toml`.

The example uses `AWS_REGION=ap-south-1` (Mumbai) and
`BEDROCK_MODEL_ID=apac.amazon.nova-micro-v1:0`. This is a cross-region inference
profile that can route requests to its supported APAC destination regions.
The AWS CLI profile selects credentials; the Bedrock inference profile
selects model routing. These are separate concepts.
Your AWS identity needs `bedrock:InvokeModel` permission for the selected model,
and the model must be accessible in your account and region. Each invocation
uses the account's Bedrock usage allowance or incurs charges.

### Run

Start the Streamlit interface locally:

```powershell
uv run -m streamlit run app.py --server.address 127.0.0.1
```

The wide layout places the prompt on the left and one scrollable output panel
on the right. The **Converse** and **ConverseStream** tabs have independent
prompts, settings, and saved results. Converse returns the complete answer;
ConverseStream displays text as chunks arrive in the same output panel.
Open **Parameters** for temperature, maximum output tokens, and
system instructions. Click **Run prompt** to invoke Bedrock. Each run is independent;
previous answers are not included in the next request. In the output panel, use
**Response**, **Request**, **Raw JSON**, or **Code snippet** to switch views. Token usage,
latency, and stop reason appear in a compact line above the answer.
Under **Raw JSON**, click **Show raw response** to display the complete response,
including response metadata; click **Hide raw response** to close it. This
button uses the saved result and does not make another API call. A new run hides
the raw response again. Changing controls alone does not invoke Bedrock. A failed run
clears the previous result so it cannot be mistaken for a new response.

For **ConverseStream**, your AWS identity needs
`bedrock:InvokeModelWithResponseStream`. The final token usage and latency come
from the stream's `metadata` event, and the stop reason comes from `messageStop`.
The streaming **Raw JSON** view shows decoded events in arrival order. The code
snippet switches to `converse_stream` and a minimal event loop, without imports.
Switching tabs or output views does not invoke a model or replay a saved stream.

The interface uses a black-and-red theme configured in `.streamlit/config.toml`,
with custom panel, widget, button, and metric styles in `styles.css`. Restart
Streamlit after changing the theme configuration.

The profile name is shown in the sidebar; credentials are never placed in the
interface, API payload display, or session state. Responses are held in the current browser
session; the app does not save them to disk. After editing `.env`, rerun or reload
the page to read the new configuration.

The command-line version is also available:

```powershell
uv run converse.py
uv run converse.py "Explain RAG versus fine-tuning with one example each."
uv run converse.py "Explain prompt injection." --max-tokens 128 --temperature 0.7
```

### Certification practice

Use **Inference profiles** in the sidebar to list system-defined profiles from
a source AWS region. **APAC** is selected by default (Mumbai / `ap-south-1`);
choose **US** for a US source region (default `us-east-1`), or enter another source
region in the selected geography. The configured `.env` region is used when it
belongs to the selected geography.

Click **List profiles** to fetch every result page using your AWS CLI profile.
The identity needs `bedrock:ListInferenceProfiles`. Results show profile IDs,
status, destination regions, raw details, and copyable `.env` settings in one
scrollable panel. Search and choose a profile from the dropdown to inspect it.
Search filters the loaded results locally. APAC shows `apac.*` profiles and US shows
`us.*`; global and country-specific routing profiles are excluded. Listing does
not invoke models or change your configuration. Model invocation still requires
its own permissions and access.

Choose **Code snippet** in the output panel for a minimal Python example: AWS
profile setup, the Converse call, and printing the answer. Open **Parameter
notes** for short definitions. Click **Preview code** after adjusting the form
to refresh the snippet without making a Bedrock call. The snippet uses your
named AWS profile and contains no keys.

- Inspect `system`, `messages`, and `inferenceConfig` in the request.
- Repeat the same prompt with temperatures of `0.0` and `0.8`; compare answers.
- Lower `--max-tokens` and observe whether the stop reason becomes `max_tokens`.
  This caps output length, not input tokens.
- Change `BEDROCK_MODEL_ID` to another accessible Converse model or inference
  profile and compare response quality, token usage, and latency. Parameter
  support varies by model; this starter expects text and system prompt support
  plus the `maxTokens` and `temperature` controls.

For access errors, check the selected AWS profile and its login session, region,
model access, and `bedrock:InvokeModel` permissions. For throttling, reduce token
limits or request frequency; the SDK already retries transient failures.

If Bedrock reports that on-demand throughput is unsupported and asks for an
inference profile, set `BEDROCK_MODEL_ID` to a profile supported from your region.
For Nova Micro in `ap-south-1`, use `apac.amazon.nova-micro-v1:0` rather than
`amazon.nova-micro-v1:0`. See [supported inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html).

References: [Boto3 Converse API](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html),
[Amazon Nova Micro](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-micro.html).

## Project 2: Bedrock Chat Gateway

The **Bedrock Chat Gateway** page sends independent prompts to an IAM-authenticated
API Gateway HTTP API. A Python Lambda calls Bedrock Converse and returns JSON with
`answer`, `usage`, and `stopReason`. The page signs requests with the chosen local
AWS profile. The API URL is supplied on the page after deployment. CORS is restricted
to a configured origin; CORS does not grant access, and callers also need IAM permission.

The reusable SAM template is in `gateway/template.yaml`. It creates an HTTP API,
Lambda function, execution role, a DynamoDB history table, and two CloudWatch log groups with 14-day retention.
For each successful model response, the function saves the prompt, answer, model ID, UTC timestamp,
and Lambda request ID in DynamoDB. The `ConversationHistoryTable` stack output identifies the table.
Requests remain independent; history is not sent back to Bedrock or displayed in the page.
If the history write fails, the gateway returns an error after model invocation.
The table uses on-demand billing and point-in-time recovery and is retained on stack deletion
or replacement; delete it separately when its contents are no longer needed. Restrict access to
the table because it contains prompt and response text. CloudWatch logs contain request IDs and error codes, not prompt text. Account-level Bedrock
invocation logging, if enabled separately, can still capture prompts and responses.
The API applies stage throttling, and the Lambda caps input at 16,000 characters and
output at 512 tokens. Calls taking longer than the gateway timeout can fail; this is a
single-response endpoint, not a streaming or multi-turn chat API.

### Deploy the gateway

Complete Project 1 setup first. Install the [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
and ensure your AWS profile can deploy CloudFormation stacks, create the template's
resources and IAM role, and access the SAM deployment bucket. Deployment and model
invocations can incur AWS charges. Docker is only needed for container-based SAM
builds or local invocation; the commands below use a normal local build.

From the repository root, run:

```powershell
uv run python -m unittest discover -s gateway/tests -v
sam validate --lint --template-file gateway/template.yaml
sam build --template-file gateway/template.yaml
```

The unit tests mock Bedrock and DynamoDB and need no AWS resources. The build installs the Lambda
dependency. For the example APAC profile, query Bedrock for the profile ARN and
all its destination model ARNs, using your own AWS CLI profile and source region:

```powershell
aws bedrock get-inference-profile --profile your-profile --region ap-south-1 --inference-profile-identifier apac.amazon.nova-micro-v1:0 --query "[inferenceProfileArn,models[*].modelArn]" --output json
```

The first value is the inference profile ARN; the nested list contains the model
ARNs. Join **all** of them into one comma-separated string with no brackets or
quotes. The account ID in the profile ARN must be your own. Destination regions can
change, so query again when updating a deployment. For a different model or profile,
discover its applicable resources and permissions for your account and region.

`samconfig.toml` holds account-specific settings, so Git ignores it and it is not in this
repository. The guided setup below creates it for you; `samconfig.toml.example` shows the
shape if you prefer to write it by hand. Run the guided setup:

```powershell
sam deploy --guided --template-file .aws-sam/build/template.yaml --profile your-profile
```

Review and replace every suggested value that does not match your environment:

- **Stack Name** and **AWS Region**: choose your stack name and the source region
  used in the profile query.
- **ModelId**: the profile ID, such as `apac.amazon.nova-micro-v1:0`.
- **ModelResourceArns**: the comma-separated profile and destination model ARNs
  from your query. Do not leave either model parameter blank.
- **AllowedOrigin**: the exact browser origin, for example `http://localhost:8501`.
- Allow SAM to create the IAM role, save the configuration, and review the
  CloudFormation changeset before confirming it. The named CLI profile must be
  authorized for the target account.

Guided deployment saves parameters in `samconfig.toml`; inspect it before subsequent
deployments. Never commit or share it, since it contains your account ID and local settings.
Use `sam build --template-file gateway/template.yaml` followed by `sam deploy`
for subsequent deployments after checking those saved values.

Copy the deployed stack's outputs into `.env` (use your own values):

```dotenv
GATEWAY_URL=https://YOUR_API_ID.execute-api.YOUR_REGION.amazonaws.com/prod/explain
GATEWAY_INVOKE_ARN=arn:aws:execute-api:YOUR_REGION:YOUR_ACCOUNT_ID:YOUR_API_ID/prod/POST/explain
```

Use `ExplainUrl` for `GATEWAY_URL` and `InvokeArn` for `GATEWAY_INVOKE_ARN`.
The gateway page displays both and uses the URL as an editable default. It also
defaults to `AWS_PROFILE` from `.env`.

Grant the Streamlit caller's IAM identity `execute-api:Invoke` on that exact
`InvokeArn`; deployment does not modify caller identities. For example, an
administrator can add this identity policy, replacing the resource with your output:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "execute-api:Invoke",
    "Resource": "arn:aws:execute-api:YOUR_REGION:YOUR_ACCOUNT_ID:YOUR_API_ID/prod/POST/explain"
  }]
}
```

The Lambda role has separate `bedrock:InvokeModel` permission on the supplied ARNs;
this is the IAM permission required by the Converse API. Start Streamlit using the
command above, open **Bedrock Chat Gateway**, verify the URL and AWS profile, enter a
prompt, and select **Send prompt**. If you get HTTP 403, check the caller's permission
and credentials. The gateway uses non-streaming Converse. ConverseStream additionally
requires `bedrock:InvokeModelWithResponseStream` and a streaming implementation.

When finished, run `sam delete` from the repository root with your configured stack,
region, and profile, and review the confirmation. Deleting the stack retains the DynamoDB history table and does not remove
the local `.env` or caller IAM policy.
