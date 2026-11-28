# Other AWS services

The AWS services around Bedrock that a generative AI application leans on. Services with enough material have their own page; the rest are one row each.

!!! note "What was checked"
    The Step Functions and Bedrock Flows entries were checked against AWS documentation. The other rows are general summaries without service limits; check the current documentation before relying on a detail.

| Service | What it is | Role in a GenAI application | Choose it when |
|---|---|---|---|
| [Amazon Bedrock](../bedrock/index.md) | Managed foundation models and the features around them | The models, retrieval, guardrails, prompts and monitoring | Always, in this exam |
| [AWS Step Functions](step-functions.md) | Workflows built from states, run as executions | Control plane around Bedrock, Lambda and tool calls | You need durable state, parallel branches, conditions, retries, and execution history |
| [Amazon Bedrock Flows](step-functions.md#amazon-bedrock-flows) | A visual builder that links prompts, models, knowledge bases and Lambda | Prompt chaining and conditional GenAI composition | The main need is the prompt composition, not workflow controls |
| AWS Lambda | Event-driven function compute | Glue: tool implementations, validation, custom chunking, Step Functions tasks | Steps are short and stateless |
| Amazon API Gateway | Managed API front door | Authentication, throttling and request validation in front of the app | You expose the application as an API |
| Amazon EventBridge | Event bus and scheduler | Event-driven triggers, schedules, outbound API destinations | You route events or run things on a schedule |
| Amazon SQS | Message queue | Smooths bursts, rate-limits work such as embedding backfills, holds failed work in a dead-letter queue | A producer must be decoupled from a rate-limited consumer |
| Amazon DynamoDB | Key-value and document database | Session state, audit records, prompt registries, cache entries, with TTL expiry | You look things up by key at low latency |
| Amazon S3 | Object storage | Source documents, asynchronous model output, large invocation-log bodies, evaluation datasets | You need durable object storage |
| Amazon OpenSearch Serverless | Managed search and vector engine | Vector and keyword store for Knowledge Bases or direct queries | You need hybrid search with rich filters |
| Amazon CloudWatch and AWS X-Ray | Metrics, logs and alarms; distributed tracing | Latency, token and error metrics; traces across the call chain | You need to see and alarm on behaviour |
| AWS CloudTrail | API activity audit | Who called which Bedrock API, and when. It does not record prompt text. | You must prove who did what |
| AWS KMS and VPC endpoints | Encryption keys; private connectivity | Encrypt data at rest and keep Bedrock traffic off the public internet | Compliance requires encryption control or private paths |
