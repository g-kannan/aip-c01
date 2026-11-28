# AIP-C01 study site

Notes, diagrams, slide decks and labs for the AWS Certified Generative AI Developer – Professional exam, organised by service. Use the tabs at the top to move between areas, and search (press `/` or `s`) to find a topic across every page, including the text of every slide.

<div class="grid cards" markdown>

- **[Amazon Bedrock](bedrock/index.md)**

    [Inference APIs](bedrock/inference.md) · [Knowledge Bases](bedrock/knowledge-bases.md) · [Chunking](bedrock/chunking-configuration.md) · [Guardrails](bedrock/guardrails.md) · [Prompt management](bedrock/prompt-management.md) · [Monitoring and logging](bedrock/monitoring-and-logging.md) · [Caching](bedrock/caching.md) · [Cost and quota](bedrock/cost-and-quota.md)

- **[Other AWS services](services/index.md)**

    [AWS Step Functions](services/step-functions.md) and Bedrock Flows, plus one-line summaries of Lambda, EventBridge, SQS, DynamoDB and the rest.

- **[Exam map](exam-domains.md)**

    Every exam domain and task, with the slides and demos that cover it, and the gaps.

- **[Diagrams](diagrams.md) and [gotchas](gotchas.md)**

    Every diagram and trap card in one place. Each service page also links the ones it needs.

- **[Slide decks](decks/index.md)**

    Fourteen decks, each readable here as a page with one section per slide and its speaker notes.

- **[Labs and setup](labs.md)**

    The two Streamlit apps and how to run them.

</div>

!!! note "What the site does not run"
    The labs call AWS, so they cannot run on a static site. Run them locally with `uv run -m streamlit run app.py` and `uv run -m streamlit run exam_app.py`.
