# Vector stores for Knowledge Bases: OpenSearch Serverless vs S3 Vectors

For a customer-managed Knowledge Base, `CreateKnowledgeBase` takes the embedding model and the vector store in two separate places. This page compares the two stores the exam keeps pairing: **Amazon OpenSearch Serverless** and **Amazon S3 Vectors**.

Field names below were checked against the installed botocore `bedrock-agent` model. Limits and behavior come from the AWS pages listed under Sources.

## Where the choice goes

| What | Field |
|---|---|
| Embedding model | `knowledgeBaseConfiguration.vectorKnowledgeBaseConfiguration.embeddingModelArn` |
| Embedding data type (float or binary) | `...vectorKnowledgeBaseConfiguration.embeddingModelConfiguration.bedrockEmbeddingModelConfiguration.embeddingDataType` (`FLOAT32` or `BINARY`) |
| Vector store | `storageConfiguration.type`, plus the matching child object |

`storageConfiguration.type` accepts `OPENSEARCH_SERVERLESS`, `OPENSEARCH_MANAGED_CLUSTER`, `RDS`, `S3_VECTORS`, `PINECONE`, `REDIS_ENTERPRISE_CLOUD`, `MONGO_DB_ATLAS` and `NEPTUNE_ANALYTICS`. Send only the child object that matches the type.

```json
{"type": "OPENSEARCH_SERVERLESS",
 "opensearchServerlessConfiguration": {
   "collectionArn": "arn:aws:aoss:us-east-1:111122223333:collection/abc123",
   "vectorIndexName": "kb-index",
   "fieldMapping": {"vectorField": "embedding", "textField": "text", "metadataField": "metadata"}}}
```

```json
{"type": "S3_VECTORS",
 "s3VectorsConfiguration": {
   "indexArn": "arn:aws:s3vectors:us-east-1:111122223333:bucket/my-vectors/index/kb-index"}}
```

For OpenSearch, all three `fieldMapping` fields are required, and the index you create must already contain a vector field, a text field and a metadata field with those names. For S3 Vectors, none of the child fields is marked required in the API model: give either `indexArn`, or `vectorBucketArn` with `indexName`.

## Side by side

| | OpenSearch Serverless | S3 Vectors |
|---|---|---|
| Search types | Semantic **and hybrid** (needs a filterable text field) | **Semantic only**. No hybrid search. |
| Binary embeddings | **Supported.** OpenSearch Serverless and managed clusters are the only stores that hold binary vectors. | **Not supported.** Float only. |
| Cluster to run | None. Serverless collection, billed in OCUs. | None. A vector bucket and a vector index. |
| Cost shape | An OCU floor, so there is a standing cost even when idle | Pay for storage and requests. No idle compute. |
| Latency | Lowest of the two; built for high query rates | Higher; best for infrequent or latency-tolerant queries |
| Metadata per vector | Rich. Bedrock uses a vector, text and metadata field. | Tight: 1 KB of custom metadata and 35 keys per vector in a Knowledge Base |
| Hierarchical chunking | Fine | Not recommended above 8,000 combined tokens. Parent-child links are stored as non-filterable metadata and can exceed the size limit. |
| Filtering | Metadata filters on ingested attributes | Metadata filters on ingested attributes. Chunk text and Bedrock's own metadata field are non-filterable, so filter on your own fields. |
| Best for | Hybrid search, binary vectors, steady or high traffic | Large, cost-sensitive collections queried rarely |

The numbers in the S3 Vectors row come from the Bedrock-specific guidance. The general S3 Vectors limits page lists larger figures (for example 40 KB total metadata per vector). In a Knowledge Base, treat the smaller Bedrock figures as the binding ones, and re-check both before relying on them.

## How the deciding constraint plays out

A typical exam stem: *the team uses binary vector embeddings, wants no cluster to manage, and wants to keep the Bedrock Knowledge Bases API.*

1. Binary embeddings remove every store except OpenSearch Serverless and OpenSearch managed clusters.
2. "No cluster management" removes the managed cluster.
3. That leaves **OpenSearch Serverless**: `type: OPENSEARCH_SERVERLESS`, `embeddingDataType: BINARY`.

S3 Vectors is the tempting wrong answer, because it also has no cluster and is cheaper. It fails on binary support, and again if the stem asks for hybrid search.

Flip the stem (float embeddings, millions of vectors, queried a few times a day, minimize cost, semantic search is enough) and S3 Vectors wins.

| Requirement in the stem | Pick |
|---|---|
| Binary vector embeddings | OpenSearch Serverless (or a managed cluster) |
| Hybrid keyword plus vector search | OpenSearch Serverless |
| No cluster to operate | OpenSearch Serverless or S3 Vectors |
| Lowest cost for rarely queried data | S3 Vectors |
| High query rate, low latency | OpenSearch Serverless |
| Hierarchical chunking with large parents | OpenSearch Serverless, or keep S3 Vectors under 8,000 combined tokens |

## Hierarchical chunking on each store

Hierarchical chunking retrieves the small child chunks first, then swaps each one for its larger parent before the text reaches the model. Two effects follow, on either store:

- Several children can share one parent, so the number of chunks returned can be **lower** than the number you requested.
- The parent context is bigger, so prompts grow.

On S3 Vectors there is a third. The parent-child relationship and its context are written as non-filterable metadata, which counts against the per-vector metadata budget. Large parent plus child token counts can exceed it, which is why AWS does not recommend hierarchical chunking there above 8,000 combined tokens. See [Chunking configuration](chunking-configuration.md) and the [gotcha card](../gotchas/hierarchical-chunking-s3-vector-bucket.svg).

## Setting up the store yourself

- **OpenSearch**: create the collection and the vector index first. The index needs the vector field (with the right dimension and space type), the text field and the metadata field that your `fieldMapping` names. For binary vectors, use the `hamming` space type rather than `l2`, and a binary vector field type. AWS documents an engine version of 2.16 or later for binary vectors on managed clusters.
- **S3 Vectors**: create the vector bucket and the index. The index dimension must match the embedding model's output. Metadata keys marked non-filterable at index creation cannot be changed to filterable later.

## Known limits

- Hybrid search is documented for RDS, OpenSearch Serverless and MongoDB, and Knowledge Bases quietly fall back to semantic search on other stores. Test it, as [Knowledge Bases](knowledge-bases.md#search-settings) notes.
- I did not verify cost figures. Sources disagree on the OpenSearch Serverless OCU minimum, so check the current pricing page rather than quoting a dollar amount.
- One AWS blog says newer OpenSearch Serverless collection types may not yet work with the Knowledge Bases `Retrieve` API. I found that in a single source and did not confirm it, so check before choosing a collection type.
- Re-check all of this against the current documentation before an exam or a release.

Sources: [CreateKnowledgeBase](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_CreateKnowledgeBase.html), [StorageConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_StorageConfiguration.html), [Prerequisites for a vector store you created](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html), [Using S3 Vectors with Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-bedrock-kb.html), [Binary vector embeddings announcement](https://aws.amazon.com/about-aws/whats-new/2024/11/amazon-bedrock-knowledge-bases-binary-vector-embeddings-rag-applications), [Selecting a vector store for Bedrock Knowledge Bases](https://aws.amazon.com/blogs/machine-learning/selecting-a-vector-store-for-amazon-bedrock-knowledge-bases/).
