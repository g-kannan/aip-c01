# Diagrams

Click a diagram to zoom. Each one has a full text description for screen readers in the SVG itself.

## Chunking strategies

![Five ways Amazon Bedrock Knowledge Bases split a document into chunks](images/bedrock-kb-chunking.svg)

Default, fixed-size, hierarchical, semantic, and no chunking, with the settings each one takes. For the API fields, ranges and how to choose, see [Chunking configuration](bedrock/chunking-configuration.md).

## Token quota burndown

![How Amazon Bedrock counts a request against tokens-per-minute quota](images/bedrock-token-burndown.svg)

How a request is reserved against the tokens-per-minute quota and settled afterwards. See also the [`max_tokens` gotcha](gotchas.md).

## HNSW search

![How an HNSW index finds nearest neighbors by hopping down layers](images/hnsw-search.svg)

The layered graph an HNSW index walks, from sparse upper layers down to the dense bottom layer.

## KNN versus HNSW

![KNN versus HNSW for nearest-neighbor vector search](images/knn-vs-hnsw.svg)

Exact nearest-neighbor search compared with the approximate graph search.

## Prompt caching versus semantic caching

![Prompt caching reuses the input; semantic caching reuses the answer](images/prompt-vs-semantic-caching.svg)

Prompt caching reuses the processed prefix and still runs the model. Semantic caching reuses a stored answer and may skip the model. The slide for this is in [deck 04](slides/04-agent-cost-models-tokens/index.html).
