# Gotchas

Four details that are easy to get wrong. Each card states the trap, the fix, and the rule to remember.

## Hierarchical chunking on S3 vector buckets

![Gotcha: hierarchical chunking is not recommended on S3 vector buckets above 8,000 combined tokens](gotchas/hierarchical-chunking-s3-vector-bucket.svg)

See [Chunking configuration](bedrock/chunking-configuration.md) for the hierarchical fields.

## `max_tokens` reserves quota

![Gotcha: max_tokens is reserved against tokens-per-minute quota at the start of a request](gotchas/max-tokens-reserves-quota.svg)

See the [token quota burndown diagram](diagrams.md#token-quota-burndown).

## Prompt routing is English-only

![Gotcha: Intelligent Prompt Routing is only optimized for English prompts](gotchas/prompt-routing-english-only.svg)

## A router needs two models from one family

![Gotcha: a router must hold exactly two models from the same family](gotchas/router-same-family.svg)
