# AIP-C01 exam domains, tasks, and repo coverage

Source: the official AWS Certified Generative AI Developer – Professional (AIP-C01) exam guide.
Tick a task when you can explain it **and** have seen it work (a lab, a demo, or a slide you could teach from).

**Coverage key** — what this repo gives you today:

- **Lab** = a runnable Streamlit page or deployable stack
- **Slides** = a deck in `slides/`
- **Gap** = not covered, or covered by slides only

| Domain | Weight |
|---|---|
| 1. Foundation Model Integration, Data Management, and Compliance | 31% |
| 2. Implementation and Integration | 26% |
| 3. AI Safety, Security, and Governance | 20% |
| 4. Operational Efficiency and Optimization for GenAI Applications | 12% |
| 5. Testing, Validation, and Troubleshooting | 11% |

## Domain 1 — Foundation Model Integration, Data Management, and Compliance (31%)

- [ ] **Task 1.1 — Analyze requirements and design GenAI solutions**
  - Align architecture and deployment patterns to business needs and technical constraints; validate feasibility, performance, and value with a proof of concept; apply reusable standards such as the Well-Architected Framework and Generative AI Lens.
  - *Repo:* **Slides** 13 (requirements, POC, Well-Architected Generative AI Lens), 00. No demo: this is design reasoning.
- [ ] **Task 1.2 — Select and configure foundation models**
  - Compare model capabilities, benchmarks, and limitations; design provider/model switching without code changes; plan for outages, cross-Region inference, and graceful degradation; manage customization and lifecycle (including fine-tuning/adaptation, versioning, deployment, and rollback).
  - *Repo:* **Lab** (Converse Lab swaps `BEDROCK_MODEL_ID`; Inference profiles page for cross-Region; Resilience Simulator live fallback chain). **Slides** 01, 04, 09, 13. Gap: model customization lifecycle and rollback.
- [ ] **Task 1.3 — Validate and process data for model consumption**
  - Build data-quality validation; process text, images, audio, and tabular inputs; format requests to model-specific requirements; improve input quality through normalization, reformatting, and entity extraction.
  - *Repo:* **Lab** (Input Cleaner: normalization, entity extraction with regex and a model, quality gate, per-model request formats). **Slides** 08. Gap: image and audio inputs are described, not demonstrated.
- [ ] **Task 1.4 — Design and implement vector stores**
  - Choose vector-store architectures; define metadata for precision and context; plan scalable indexing and performance; connect enterprise knowledge sources; keep indexes accurate with change detection, synchronization, and refresh workflows.
  - *Repo:* **Lab** (Knowledge Base Lab: vector-store vs managed KB, `*.metadata.json` sidecars). **Slides** 08 (store trade-offs, sync and refresh). Gap: no hands-on ingestion-job demo.
- [ ] **Task 1.5 — Design retrieval for model augmentation**
  - Choose chunking/segmentation and embedding strategies; configure vector search; improve relevance with hybrid search and reranking; use query expansion, decomposition, or transformation; expose retrieval through consistent APIs, function calls, or MCP.
  - *Repo:* **Lab** (Knowledge Base Lab: Retrieve vs RetrieveAndGenerate, SEMANTIC/HYBRID, reranking, filters, citations; Chunking Playground). **Slides** 08. `resources/` holds RAG, Self-RAG, and tool-use papers. Gap: query expansion/decomposition and MCP are slides only.
- [ ] **Task 1.6 — Engineer and govern prompts**
  - Create instructions, templates, and guardrails; preserve conversational context; establish prompt versioning, approvals, and audit logs; test prompts and regressions; iteratively improve output quality; design prompt chains and conditional flows.
  - *Repo:* **Lab** (Prompt Lab: variables, immutable versions, approval, promotion and rollback, audit log, regression test, Bedrock Prompt management). **Slides** 12. Gap: Bedrock Flows are slides only.

## Domain 2 — Implementation and Integration (26%)

- [ ] **Task 2.1 — Implement agents and tool integrations**
  - Design agent memory/state and multi-agent coordination; structure complex reasoning workflows; add stopping conditions, timeouts, least-privilege boundaries, and circuit breakers; use human review where appropriate; validate tool inputs/errors; build or connect MCP servers.
  - *Repo:* **Slides** 03 (bounded loops), 09 (stopping conditions, boundaries). **Lab** (Resilience Simulator: agent guards on a scripted agent). Gap: no real agent, agent memory, multi-agent coordination, or MCP server.
- [ ] **Task 2.2 — Implement model deployment strategies**
  - Match deployment options to workload needs (on-demand, provisioned throughput, or endpoints); account for LLM memory, GPU, loading, and token-processing requirements; optimize cost and performance through model choice, smaller models, and cascading.
  - *Repo:* **Slides** 01, 04 (tiering), 13 (on-demand, provisioned, batch, import, SageMaker shapes). Gap: no deployment demo; GPU endpoints are costly.
- [ ] **Task 2.3 — Build enterprise integration architectures**
  - Connect legacy and enterprise systems with APIs, events, and synchronization; embed GenAI into applications and microservices; apply federation, RBAC, and least privilege; design compliant hybrid/edge connectivity; build CI/CD and gateway patterns with automated tests, security scans, and rollback.
  - *Repo:* **Lab** (Bedrock Chat Gateway: HTTP API + IAM auth + Lambda + DynamoDB, SAM, unit tests). **Slides** 02, 13. Gap: events, CI/CD pipeline and federation are slides only.
- [ ] **Task 2.4 — Integrate foundation-model APIs**
  - Implement synchronous and asynchronous requests; support streaming and real-time interfaces; handle retries, backoff, rate limits, timeouts, fallbacks, and tracing; route requests using static rules, content, or performance signals.
  - *Repo:* **Lab** (Converse and ConverseStream, SDK retries; Resilience Simulator: backoff and jitter, thundering herd, circuit breaker, live fallback, routing). **Slides** 01, 09. Gap: asynchronous invocation.
- [ ] **Task 2.5 — Apply application patterns and developer tools**
  - Build workload-appropriate APIs and accessible interfaces; integrate GenAI into business workflows; use developer-assistance tools; implement orchestration, agents, and prompt chains; troubleshoot with logs, traces, and application-level diagnostics.
  - *Repo:* **Partial** (Streamlit UI, gateway API). **Slides** 02, 12, 13. Gap: orchestration and tracing are slides only.

## Domain 3 — AI Safety, Security, and Governance (20%)

- [ ] **Task 3.1 — Implement input and output safety controls**
  - Filter harmful inputs and outputs; ground and verify responses to reduce hallucinations; enforce structured outputs; apply defense in depth; detect prompt injection, jailbreaks, and adversarial inputs.
  - *Repo:* **Lab** (Guardrails Lab: four layers, ApplyGuardrail, create a guardrail in Detect or Enforce mode). **Slides** 06.
- [ ] **Task 3.2 — Implement data security and privacy**
  - Isolate and protect AI environments with network and identity controls; detect and protect PII; apply masking, anonymization, and privacy-preserving techniques; define retention and access monitoring.
  - *Repo:* **Lab** (Guardrails Lab PII masking; gateway least-privilege IAM, DynamoDB TTL, no prompt text in logs). **Slides** 07. Gap: VPC endpoints are slides only.
- [ ] **Task 3.3 — Implement governance and compliance**
  - Document models, data lineage, and sources; maintain traceability and audit logs; align organizational controls to policies and regulations; monitor misuse, drift, and policy violations and automate alerts/remediation.
  - *Repo:* **Slides** 07. **Lab** (Prompt Lab audit log; gateway history; KB metadata records sources). Gap: model cards, lineage and alerting are slides only.
- [ ] **Task 3.4 — Apply responsible AI principles**
  - Make outputs transparent with explanations, confidence, and source attribution; evaluate fairness and bias; document model limitations; enforce policy requirements through automated checks and controls.
  - *Repo:* **Slides** 05, 07 (safety metrics, transparency, fairness). **Lab** (KB Lab source attribution). Gap: no runnable fairness test.

## Domain 4 — Operational Efficiency and Optimization for GenAI Applications (12%)

- [ ] **Task 4.1 — Optimize cost and resource efficiency**
  - Track and reduce token use with context management, prompt compression, and response limits; balance model cost against capability; plan capacity, batching, and scaling; use caching to avoid redundant inference.
  - *Repo:* **Slides** 03, 04 (token levers, three-layer caching). **Lab** (token usage and `maxTokens` visible; Eval Harness reports tokens and cost). Gap: no measured caching demo.
- [ ] **Task 4.2 — Optimize application performance**
  - Balance latency, quality, and cost with precomputation, streaming, parallelism, and benchmarking; optimize retrieval and vector queries; improve throughput and concurrency; tune model parameters and resource allocation for workload patterns.
  - *Repo:* **Lab** (latency display, streaming; Eval Harness p50 and p95). **Slides** 10. Gap: retrieval tuning.
- [ ] **Task 4.3 — Monitor GenAI applications**
  - Build observability for operations and business outcomes; monitor tokens, prompt effectiveness, quality, hallucinations, drift, cost, and latency; trace model, agent, and tool calls; maintain vector-store health; use golden datasets, output diffs, and reasoning traces to diagnose GenAI-specific failures.
  - *Repo:* **Slides** 10 (metrics, logs, traces, drift). **Lab** (Eval Harness scorecard). Gap: nothing in this repo is instrumented with CloudWatch or X-Ray.

## Domain 5 — Testing, Validation, and Troubleshooting (11%)

- [ ] **Task 5.1 — Evaluate GenAI systems**
  - Assess relevance, factual accuracy, consistency, and fluency; compare models/configurations with A/B and canary tests; gather user feedback; run continuous regression checks and deployment gates; evaluate RAG, retrieval, and agent performance; report results and validate updates with synthetic workflows and drift/hallucination checks.
  - *Repo:* **Slides** 05, 11. **Lab** (Eval Harness: golden dataset, A/B, optional LLM judge, release gate). Gap: Bedrock Evaluation jobs are not run.
- [ ] **Task 5.2 — Troubleshoot GenAI applications**
  - Diagnose context overflow, truncation, and chunking problems; resolve API/request/response integration errors; systematically test and refine prompts; investigate retrieval, embeddings, indexing, and drift; use logs, tracing, and schema validation to maintain prompt templates and output consistency.
  - *Repo:* **Slides** 11. **Lab** (Chunking Playground: missing exception, context overflow; KB Lab `error_hint`; `max_tokens` stop-reason experiment).

## What the exam material contains

Two apps and a set of decks, each independent of the others.

**Slides** (`slides/index.html` lists them; open any deck in a browser):

| Deck | Topic | Tasks |
|---|---|---|
| 00 | Exam map | all |
| 01 | Bedrock inference APIs | 1.2, 2.4 |
| 02 | AWS SAM | 2.3 |
| 03, 04 | Agent cost: loops, models and tokens | 2.1, 2.2, 4.1 |
| 05 | Evaluation metrics | 5.1 |
| 06 | Guardrails and defense in depth | 3.1 |
| 07 | Privacy, governance, responsible AI | 3.2, 3.3, 3.4 |
| 08 | Data to retrieval | 1.3, 1.4, 1.5 |
| 09 | Resilience and routing | 1.2, 2.1, 2.4 |
| 10 | Observability and performance | 4.2, 4.3 |
| 11 | Evaluate and troubleshoot | 5.1, 5.2 |
| 12 | Prompt governance | 1.6 |
| 13 | Design and deploy | 1.1, 2.2, 2.3 |

**Demos** (`uv run -m streamlit run exam_app.py`, separate from `app.py`): Guardrails Lab, Prompt Lab, Chunking
Playground, Input Cleaner, Resilience Simulator, Eval Harness. Logic lives in `exam_labs/` and is unit-tested in
`tests/test_exam_labs.py`; the pages call Bedrock through the same `.env` profile as the main app.

## Known limits

- Decks 06 to 13 were written from general AWS knowledge. Each slide's speaker notes say where to verify against the
  current documentation; check service limits, metric names and supported models before relying on them.
- The Bedrock calls in the demos (ApplyGuardrail, create guardrail, Prompt management, Converse, the eval runs) were
  verified against the installed `boto3` API shapes and with mocked tests, not against a live account.
- Creating a guardrail or a prompt in the demos makes real AWS resources. Delete them in the console afterwards.
