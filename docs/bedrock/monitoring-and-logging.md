# Monitoring and logging

Bedrock gives two different views. Runtime metrics tell you that something is wrong. Invocation logs tell you what was sent and returned.

| | Runtime metrics | Model invocation logs |
|---|---|---|
| Where | CloudWatch, namespace `AWS/Bedrock` | CloudWatch Logs, Amazon S3, or both |
| What | Invocations, latency, token counts, client and server errors, throttles, time to first token for streaming | The full request, response and metadata for each call |
| Default | Published automatically | Disabled. Turn it on per account and Region. |
| Use for | Alarms and dashboards | Request and response evidence, investigations, evaluation input |
| Cannot do | Calculate semantic KPIs such as hallucination rate or prompt effectiveness | Alarm by itself; build metric filters or evaluations on top |

## Runtime metrics

- **Publishing:** metrics are published both with and without the `ModelId` dimension. A request that fails before Bedrock knows which model it targets is published only without `ModelId`, so filtering by `ModelId` undercounts errors.
- **Fleet alarms:** alarm on `InvocationClientErrors`, `InvocationServerErrors` and `InvocationThrottles` with no `ModelId` filter. Keep `ModelId` for per-model dashboards.
- **`Invocations` is not a failure total:** it counts requests accepted for processing, including ones that later failed. It excludes throttled requests and requests rejected during input validation.
- **Throttles:** they are not counted in `Invocations`, `InvocationClientErrors` or `InvocationServerErrors`, and their count depends on SDK retry settings. Requests rejected for exceeding a service quota are client errors, not throttles.
- **Streaming:** `TimeToFirstToken` is published for `ConverseStream` and `InvokeModelWithResponseStream` only.

## Model invocation logging

- **Scope:** disabled by default, and configured per account and Region with `PutModelInvocationLoggingConfiguration`. Only calls through the `bedrock-runtime` endpoint are captured.
- **Destinations:** CloudWatch Logs, Amazon S3, or both, and only in the same account and Region.
- **Contents:** each record has `requestId`, `operation`, `modelId`, `identity.arn`, `requestMetadata` (when the caller sends it), the input and output bodies, and token counts.
- **Sensitive data:** the `input` field holds the original request even when a guardrail masked it, so restrict access and protect the logs. See [Guardrails](guardrails.md).

### The 100 KB limit

Log events hold input and output JSON bodies only up to 100 KB. Binary data, and JSON bodies larger than 100 KB, need an S3 location for large-data delivery: they are written as separate objects under the `data` prefix, and the log entry points to them.

So if the largest prompts are missing from CloudWatch Logs, the cause is the 100 KB limit, and the fix is to configure S3 large-data delivery. AWS says only S3 is supported for large data. It does not say what happens to a large body when no S3 location is set, so do not rely on CloudWatch Logs alone for long prompts.

## Tag every call

Send `requestMetadata` with each call so logs can be grouped by release:

| Topic | Fact |
|---|---|
| How to send it | `Converse` and `ConverseStream`: the `requestMetadata` body field. `InvokeModel` and `InvokeModelWithResponseStream`: the `X-Amzn-Bedrock-Request-Metadata` header, as a JSON object. |
| Limits | Up to 16 entries; keys and values up to 256 characters each |
| Where it appears | A top-level `requestMetadata` field in invocation logs, only when logging is enabled in the Region where the call is made |
| What it is not | Enforced (requests without it still succeed), or a cost allocation tag (it does not appear in Cost Explorer) |
| SigV4 | The header must be in the signed headers |

Put the prompt version, or a release ID, in it. Then token usage and quality investigations can be grouped by version; see [Prompt management](prompt-management.md#connect-a-release-to-the-evidence).

## Go deeper

- Slides: [Watch four things, not one](../decks/10-observability-and-performance.md#watch-four-things-not-one), [What Bedrock publishes to CloudWatch](../decks/10-observability-and-performance.md#what-bedrock-publishes-to-cloudwatch), [Alarm on the fleet, not one model](../decks/10-observability-and-performance.md#alarm-on-the-fleet-not-one-model), [Model invocation logging](../decks/10-observability-and-performance.md#model-invocation-logging), [Tag every call with its prompt version](../decks/10-observability-and-performance.md#tag-every-call-with-its-prompt-version), [Follow one request through every hop](../decks/10-observability-and-performance.md#follow-one-request-through-every-hop), [Logs are data too](../decks/07-privacy-and-governance.md#logs-are-data-too)
- Quality, which metrics cannot measure: [deck 05](../decks/05-bedrock-evaluation-metrics.md) and [deck 11](../decks/11-evaluate-and-troubleshoot.md)

Sources: [Monitor runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-cw.html), [Model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html), [Per-request metadata tagging](https://docs.aws.amazon.com/bedrock/latest/userguide/cost-mgmt-request-metadata.html).
