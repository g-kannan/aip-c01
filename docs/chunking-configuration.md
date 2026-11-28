# Chunking configuration for Bedrock Knowledge Bases

Source: the AWS API reference for [ChunkingConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_ChunkingConfiguration.html) and its child pages (FixedSize, Hierarchical, HierarchicalLevel, Semantic). Every range and required flag below was checked against the installed botocore `bedrock-agent` model, and the example configs are tested in `tests/test_exam_labs.py` (`RequestShapeTests`).

This page covers the API shape and how to choose. For the five-way picture, see [`docs/images/bedrock-kb-chunking.svg`](images/bedrock-kb-chunking.svg). For the classic failure, see the [S3 vector bucket gotcha](gotchas/hierarchical-chunking-s3-vector-bucket.svg).

## Where it goes

`ChunkingConfiguration` is set per data source at ingestion, under `CreateDataSource` → `vectorIngestionConfiguration.chunkingConfiguration`. Chunks are created once, when documents are ingested. Changing the strategy does not change chunks that already exist.

Custom chunking through a Lambda is not a `chunkingStrategy` value. It lives in the sibling `customTransformationConfiguration`.

## Shape

`chunkingStrategy` is required. Send only the child object that matches the strategy. `NONE` takes no child object.

| `chunkingStrategy` | Child object | Required fields (range) |
|---|---|---|
| `FIXED_SIZE` | `fixedSizeChunkingConfiguration` | `maxTokens` (1–8192), `overlapPercentage` (1–99) |
| `HIERARCHICAL` | `hierarchicalChunkingConfiguration` | `levelConfigurations` (exactly 2 items, each `maxTokens` 1–8192; first is the large parent layer, second the small child layer), `overlapTokens` (min 1) |
| `SEMANTIC` | `semanticChunkingConfiguration` | `maxTokens` (1–8192), `bufferSize` (0–1), `breakpointPercentileThreshold` (50–99) |
| `NONE` | none | none |

Two limits are easy to miss:

- `overlapPercentage` and `overlapTokens` both start at 1. The API cannot express zero overlap for these strategies.
- The AWS page gives no defaults. Do not assume one; always send the strategy explicitly.

## Examples

These are the configs in `exam_labs/chunking.py` (`CHUNKING_CONFIGS`), which the tests validate.

```json
{"chunkingStrategy": "FIXED_SIZE",
 "fixedSizeChunkingConfiguration": {"maxTokens": 300, "overlapPercentage": 20}}
```

```json
{"chunkingStrategy": "HIERARCHICAL",
 "hierarchicalChunkingConfiguration": {
   "levelConfigurations": [{"maxTokens": 1500}, {"maxTokens": 300}],
   "overlapTokens": 60}}
```

```json
{"chunkingStrategy": "SEMANTIC",
 "semanticChunkingConfiguration": {"maxTokens": 300, "bufferSize": 1, "breakpointPercentileThreshold": 95}}
```

```json
{"chunkingStrategy": "NONE"}
```

## How semantic chunking decides where to split

- Each sentence is compared with the next one, using a model at ingestion. That comparison is the extra cost and latency.
- `breakpointPercentileThreshold` sets how many adjacent pairs are split. A threshold of 90 splits the 10% of pairs that are least similar. With 101 sentences there are 100 pairs, so 10 splits give 11 chunks. A higher threshold means fewer splits and larger chunks. A lower one means more, smaller chunks.
- `bufferSize: 0` embeds each sentence alone. `bufferSize: 1` embeds each sentence together with its neighbors, so the boundary is smoother but less sharp.
- `maxTokens` still applies. Any semantic chunk that is too long is split again.

## Choosing a strategy

Work through these in order. Stop at the first one that fits.

1. **Is each file already one answer?** (an FAQ entry, one record per file, a short ticket.) Use `NONE`. Nothing can split a rule from its exception. The cost is that a long file becomes one vector, and citations lose page-level detail. Split files before ingesting if they are long.
2. **Do answers depend on nearby text?** (a procedure followed by its exception.) Use `HIERARCHICAL`. Small children match precisely, and the larger parent gives the model the context around the match. The cost is bigger prompts, and the S3 vector bucket limit of 8,000 combined tokens. Check the vector store first.
3. **Is the structure weak?** (no headings, long prose, topics that shift mid-section.) Use `SEMANTIC`, if you can pay for the ingestion. Boundaries follow meaning rather than token count. The cost is the model calls at ingestion, and the results depend on the threshold, so test a few values.
4. **Otherwise, start with `FIXED_SIZE`.** It is cheap, predictable, and the baseline to beat. Overlap helps boundary cases but adds index size. Add complexity only when measurement shows fixed size missing answers.

| Strategy | Pick it because | What it costs you | Try it in the repo |
|---|---|---|---|
| `NONE` | The file is already the unit you want to retrieve | Whole file is one vector; weak citations | Slide 08, chunking table |
| `FIXED_SIZE` | Simple, cheap, and the baseline | Splits rules from exceptions; overlap costs index size | Chunking Playground, "Fixed size" |
| `HIERARCHICAL` | Precise match plus surrounding context | Two levels only; bigger prompts; S3 vector bucket limit | Chunking Playground, "Hierarchical"; gotcha card |
| `SEMANTIC` | Topic shifts matter more than length | Model calls at ingestion; threshold needs tuning | Slide 08 notes; diagram |

Whichever you pick, measure it the way the Chunking Playground does. Check whether the exception is in the context sent to the model, not just whether the chunk looks right.

## Known limits

- The repo's five-way diagram gives a default of about 300 tokens with sentences kept whole. That is not on the API page, and I did not verify it against the Knowledge Base chunking docs. Check before relying on it.
- The diagram says semantic chunking uses a foundation model. Slide 08 says an embedding model. Check the current Knowledge Base docs and fix whichever one is wrong.
- Re-check these limits against the current documentation before an exam or a release. AWS changes ranges and defaults.
