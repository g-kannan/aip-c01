# AIP-C01 study site

Notes, diagrams, slide decks and labs for the AWS Certified Generative AI Developer – Professional exam. Use the search box (press `/` or `s`) to find a topic across every page.

<div class="grid cards" markdown>

- **[Exam map](exam-domains.md)**

    Every exam domain and task, with the slides and demos that cover it, and the gaps.

- **[Supporting services](supporting-services.md)**

    Step Functions, Bedrock Flows, Lambda, EventBridge, SQS and the rest, and how to choose an orchestrator.

- **[Chunking configuration](chunking-configuration.md)**

    The Knowledge Base `ChunkingConfiguration` API fields and ranges, and how to choose a strategy.

- **[Diagrams](diagrams.md)**

    Chunking strategies, token quota burndown, HNSW search, KNN versus HNSW, prompt versus semantic caching.

- **[Gotchas](gotchas.md)**

    Four traps that cost points: hierarchical chunking on S3 vectors, `max_tokens` and quota, prompt routing, router pairs.

- **[Slide decks](decks.md)**

    Fourteen decks, one per exam topic, each with speaker notes.

- **[Labs and setup](labs.md)**

    The two Streamlit apps and how to run them.

</div>

!!! note "What the site does not run"
    The labs call AWS, so they cannot run on a static site. Run them locally with `uv run -m streamlit run app.py` and `uv run -m streamlit run exam_app.py`.
