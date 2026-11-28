# Supporting services

The AWS services around Bedrock that a generative AI application leans on. Each entry says what the service is, what it does in this kind of application, and when to choose it. The detailed section is orchestration, because that is where exam scenarios ask you to pick between Step Functions, Bedrock Flows, agents, and plain logs.

!!! note "What was checked"
    The Step Functions and Bedrock Flows entries, and the orchestration section, were checked against AWS documentation pages (linked below). The other rows are general summaries without service limits; check the current documentation before relying on a detail.

## At a glance

| Service | What it is | Role in a GenAI application | Choose it when |
|---|---|---|---|
| [AWS Step Functions](#aws-step-functions) | Workflows built from states, run as executions | Control plane around Bedrock, Lambda and tool calls | You need durable state, parallel branches, conditions, retries, and execution history |
| [Amazon Bedrock Flows](#amazon-bedrock-flows) | A visual builder that links prompts, models, knowledge bases and Lambda | Prompt chaining and conditional GenAI composition | The main need is the prompt composition, not workflow controls |
| AWS Lambda | Event-driven function compute | Glue: tool implementations, validation, custom chunking, Step Functions tasks | Steps are short and stateless |
| Amazon API Gateway | Managed API front door | Authentication, throttling and request validation in front of the app | You expose the application as an API |
| Amazon EventBridge | Event bus and scheduler | Event-driven triggers, schedules, outbound API destinations | You route events or run things on a schedule |
| Amazon SQS | Message queue | Smooths bursts, rate-limits work such as embedding backfills, holds failed work in a dead-letter queue | A producer must be decoupled from a rate-limited consumer |
| Amazon DynamoDB | Key-value and document database | Session state, audit records, prompt registries, cache entries, with TTL expiry | You look things up by key at low latency |
| Amazon S3 | Object storage | Source documents, asynchronous model output, evaluation datasets, archived logs | You need durable object storage |
| Amazon OpenSearch Serverless | Managed search and vector engine | Vector and keyword store for Knowledge Bases or direct queries | You need hybrid search with rich filters |
| Amazon CloudWatch and AWS X-Ray | Metrics, logs and alarms; distributed tracing | Latency, token and error metrics; traces across the call chain | You need to see and alarm on behaviour |
| AWS CloudTrail | API activity audit | Who called which Bedrock API, and when. It does not record prompt text. | You must prove who did what |
| AWS KMS and VPC endpoints | Encryption keys; private connectivity | Encrypt data at rest and keep Bedrock traffic off the public internet | Compliance requires encryption control or private paths |

## Orchestration: Step Functions, Flows, agents, or logs

A scenario to hold in mind: two analyses run side by side, a risk threshold decides what happens next, tool calls sometimes fail for transient reasons, and an auditor needs the execution path afterwards.

### AWS Step Functions

Step Functions lets you build workflows, called state machines, from steps called states. A running workflow is an execution. It is the control plane around the calls that do the AI work.

| Need in the scenario | Step Functions feature |
|---|---|
| Two analyses at the same time | A `Parallel` state runs each branch concurrently and waits for all of them. Its output is an array with one element per branch. |
| A risk threshold decides the path | A `Choice` state adds conditional rules. Set a `Default`, because with no matching rule and no `Default` the state machine throws an error. |
| Transient tool failures | A `Retry` rule on the state, with `IntervalSeconds`, `MaxAttempts`, `BackoffRate`, an optional `MaxDelaySeconds` and a `JitterStrategy`. |
| A fallback path when retries run out | A `Catch` rule with a `Next` state. Retriers are used first. |
| An auditable path | Standard workflows show execution history and visual debugging. |

Details worth knowing:

- **Error default:** when a state reports an error, Step Functions fails the whole execution unless a `Retry` or `Catch` handles it. `Retry` and `Catch` apply to `Task`, `Parallel` and `Map` states.
- **Retry defaults:** `IntervalSeconds` is 1, `MaxAttempts` is 3, `BackoffRate` is 2.0, and `JitterStrategy` is `NONE`. Set `FULL` to randomize each wait. A `MaxAttempts` of 0 means never retry.
- **`Parallel` failure:** if one branch fails, the whole `Parallel` state fails and its other branches are stopped. Lambda functions that were already invoked continue to run.
- **Standard or Express:** Standard suits long-running, auditable workflows (up to a year, exactly-once, execution history in Step Functions). Express suits high-event-rate work (up to five minutes, at-least-once, history sent to CloudWatch Logs). For "durable and auditable", choose Standard.
- **Calling Bedrock:** Step Functions has optimized integrations for the Bedrock `InvokeModel` and `CreateModelCustomizationJob` APIs. For anything else, a Lambda task can call Bedrock APIs, invoke a Bedrock agent alias, or call a Strands-based agent runtime. Step Functions provides the control plane around those calls.

Sources: [What is Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html), [Handling errors](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html), [Parallel](https://docs.aws.amazon.com/step-functions/latest/dg/state-parallel.html), [Choice](https://docs.aws.amazon.com/step-functions/latest/dg/state-choice.html), [Bedrock integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrock.html).

### Amazon Bedrock Flows

Bedrock Flows uses supported foundation models to build workflows by linking prompts, models and other AWS services such as Lambda and knowledge bases. You build it visually, deploy it as an immutable version behind an alias, and call it with `InvokeFlow`.

Flows is stronger when the main requirement is prompt chaining, model calls, and conditional GenAI composition. It is not the best match when operations teams need the workflow controls that state machines provide: durable orchestration, tuned retry policies, parallel branches, and an auditable execution history. That comparison is design guidance. The AWS Flows page lists no "use Flows when" rule, so treat the boundary as a judgment, not a documented limit.

Source: [Amazon Bedrock Flows](https://docs.aws.amazon.com/bedrock/latest/userguide/flows.html).

### Agent traces and router logs

Agent traces and custom router logs help developers understand what an agent did. They are observability, not orchestration. They do not replace a managed workflow service when the scenario depends on durable state, retry policies, and an auditable execution path. If the model must choose its own steps, use an agent, and wrap it in a state machine when you still need durable control around it.

### Choosing

Work down the list and stop at the first fit.

1. **A few fixed steps, such as classify then answer:** a prompt chain in code.
2. **Prompt chaining and conditional composition, built visually and versioned:** Bedrock Flows.
3. **Durable orchestration with parallel branches, conditions, retries, and execution history:** Step Functions, Standard workflows.
4. **The model must pick the steps and tools:** an agent. Add Step Functions around it for durable state and retries.
5. **Understanding what an agent did:** agent traces and logs. Use them to debug, not to orchestrate.

| Option | Pick it because | Watch for |
|---|---|---|
| Prompt chain in code | Simplest thing that works | You own retries, state and audit |
| Bedrock Flows | Visual, versioned prompt graphs | Not a substitute for state-machine controls |
| Step Functions | Durable state, `Parallel`, `Choice`, `Retry`, history | More to design; Standard versus Express matters |
| Agent | The model chooses the steps | Less predictable; needs limits and monitoring |
| Traces and logs | Developers can see behaviour | No durable state, retry policy or managed audit path |

See also the slide ["When the workflow needs a control plane"](decks/12-prompt-governance.md) in deck 12, and the resilience patterns in [deck 09](decks/09-resilience-and-routing.md).
