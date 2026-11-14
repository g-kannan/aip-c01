# AIP-C01 hands-on practice

## Project 1: Amazon Bedrock Converse

A Python script and Streamlit playground to try text prompts and inspect model responses, token
usage, service-reported latency, and the stop reason. This is a manual experiment,
not an automated answer-quality benchmark.

### Setup

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python
3.10 or newer. From this directory in PowerShell:

```powershell
uv sync
```

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. uv manages
the local `.venv` automatically; you do not need to activate it before running.

Both interfaces use your existing AWS CLI profile through a Boto3 session.
The local `.env` contains configuration only:

```dotenv
AWS_PROFILE=agent
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=apac.amazon.nova-micro-v1:0
```

No access keys, secret keys, or session tokens need to be copied into this
project. Credentials are resolved by the named profile in your existing AWS
configuration. The `.env` file remains ignored by Git.

To verify the profile from PowerShell:

```powershell
aws sts get-caller-identity --profile agent
```

If this is an IAM Identity Center (SSO) profile, renew an expired session with
`aws sso login --profile agent`. If it uses `aws login`, use
`aws login --profile agent`. The `boto3[crt]` dependency needed for these login
sessions is included in `pyproject.toml`.

The lab uses `AWS_REGION=ap-south-1` (Mumbai) and
`BEDROCK_MODEL_ID=apac.amazon.nova-micro-v1:0`. This is a cross-region inference
profile that can route requests to its supported APAC destination regions.
The AWS CLI profile `agent` selects credentials; the Bedrock inference profile
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
