# Prompt management

Prompt versions are the unit of production prompt maintenance. A draft is for iterating; a version is what an application runs, and what a regression can be traced back to.

## Draft and version

| | Draft | Version |
|---|---|---|
| Created by | Saving the prompt | Creating a version |
| What it is | The working copy. Each save updates it. | A snapshot of the prompt at a point in time, used to switch between configurations |
| Used by production | No | Yes |
| How an application calls it | Not at all | Pass the version ARN, `arn:aws:bedrock:<region>:<account>:prompt/<id>:<version>`, as `modelId` to `Converse` or `InvokeModel`, with values in `promptVariables` |

With Converse and ConverseStream, a prompt ARN call cannot also include `additionalModelRequestFields`, `inferenceConfig`, `system` or `toolConfig`; those come from the prompt.

Because production runs a named version, the team can connect a regression to a specific prompt release. Approval and promotion are your process: Bedrock gives versions and ARNs, and CloudTrail records the API calls.

## Connect a release to the evidence

1. Release a prompt as a version.
2. Send its version reference, or a release ID, in `requestMetadata` on every call.
3. Turn on model invocation logging. Each log record then carries the metadata next to the full request and response.
4. When quality or cost changes, group the logs by version and compare.

Details of step 3, including the 100 KB limit that hides the largest prompts from CloudWatch Logs, are in [Monitoring and logging](monitoring-and-logging.md).

## Authoring tools are not forensics

| Tool | What it is for | Why it is not production evidence |
|---|---|---|
| Simple prompt optimization | A fast, heuristic rewrite of a single short prompt (about 1k tokens or less) for one target model. The console shows the result side by side with the original. | It uses no evaluation data and records nothing about production calls |
| Comparing prompt variants in the console | Choosing between drafts while authoring | It compares candidates, not what ran in production |
| Bedrock Flows validation | Checking that a flow is built correctly | It checks workflow correctness, not which prompt version produced an answer |

None of these replaces prompt versions plus invocation logging when the question is "which release caused this regression?" The Flows validation page did not load when checked, so its exact checks are not confirmed here.

## Go deeper

- Slides: [Draft, version, approve, promote](../decks/12-prompt-governance.md#draft-version-approve-promote), [Prompt management](../decks/12-prompt-governance.md#prompt-management), [Who changed what, and when](../decks/12-prompt-governance.md#who-changed-what-and-when), [Regression-test before you promote](../decks/12-prompt-governance.md#regression-test-before-you-promote), [Pick the orchestrator that fits](../decks/12-prompt-governance.md#pick-the-orchestrator-that-fits)
- Orchestration: Bedrock Flows versus Step Functions is on the [Step Functions page](../services/step-functions.md#amazon-bedrock-flows)
- Lab: the Prompt Lab in [Labs and setup](../labs.md)

Sources: [Deploy prompts using Prompt management](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-management-deploy.html), [Test a prompt](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-management-test.html), [Optimize a prompt](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-management-optimize.html).
