# Amazon Bedrock

Amazon Bedrock is the managed service for calling foundation models and building on them: inference APIs, Knowledge Bases for retrieval, Guardrails, Prompt management and Flows, and the monitoring around them. Each feature below has its own page with the key facts, and links to the slides, diagrams, gotchas and labs that cover it.

| Feature | The question it answers | Page | Slides |
|---|---|---|---|
| Inference APIs | Which call: Converse, InvokeModel, streaming, or an async job? Where may the request be processed? | [Inference APIs](inference.md) | [Deck 01](../decks/01-bedrock-inference.md) |
| Sampling parameters | Which of temperature, top_p and top_k do I change, and how do I test it? | [Sampling parameters](sampling-parameters.md) | [Deck 01](../decks/01-bedrock-inference.md#pick-the-inference-api) |
| Knowledge Bases | How do I retrieve the right passages: search type, reranking, filters? | [Knowledge Bases](knowledge-bases.md) | [Deck 08](../decks/08-data-to-retrieval.md) |
| Vector stores | OpenSearch Serverless or S3 Vectors: which fits binary vectors, hybrid search, cost? | [Vector stores](vector-stores.md) | [Deck 08](../decks/08-data-to-retrieval.md#match-the-store-to-the-workload) |
| Chunking | How are documents split, and which strategy fits? | [Chunking configuration](chunking-configuration.md) | [Deck 08](../decks/08-data-to-retrieval.md#chunking-sets-the-ceiling) |
| Guardrails | What can a guardrail block or mask, and what does it miss? | [Guardrails](guardrails.md) | [Deck 06](../decks/06-guardrails-defense-in-depth.md), [deck 07](../decks/07-privacy-and-governance.md#guardrail-pii-filters-have-blind-spots) |
| Prompt management | How do I release, trace and roll back a prompt? | [Prompt management](prompt-management.md) | [Deck 12](../decks/12-prompt-governance.md) |
| Monitoring and logging | Which signal answers which question: metrics or invocation logs? | [Monitoring and logging](monitoring-and-logging.md) | [Deck 10](../decks/10-observability-and-performance.md) |
| Caching | Which cache fits, where the `cachePoint` goes, and did it hit? | [Caching](caching.md) | [Deck 04](../decks/04-agent-cost-models-tokens.md#one-reuses-the-prompt-one-the-answer) |
| Cost and quota | What drives the bill and the tokens-per-minute quota? | [Cost and quota](cost-and-quota.md) | [Decks 03](../decks/03-agent-cost-reasoning.md) and [04](../decks/04-agent-cost-models-tokens.md) |
| Evaluation | How do I score answers and gate a release? | Slides only | [Deck 05](../decks/05-bedrock-evaluation-metrics.md), [deck 11](../decks/11-evaluate-and-troubleshoot.md) |

Orchestrating Bedrock calls with retries, parallel branches and an audit trail is a job for [AWS Step Functions](../services/step-functions.md), which also compares Bedrock Flows.

## Labs

The [labs](../labs.md) call Bedrock from your account: the Converse Lab, the Knowledge Base Lab, and the exam demos (Guardrails, Prompt, Chunking, Input Cleaner, Resilience, Eval Harness).
