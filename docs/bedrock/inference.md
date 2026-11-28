# Inference APIs

All inference calls go to the `bedrock-runtime` endpoint. The choice is about message format (one format across models, or the model's own body) and delivery (one response, a stream, or a job that writes to S3).

## Pick the call

| API | Delivery | Request body | Use it for |
|---|---|---|---|
| `Converse` | One complete response | One message format across supported models | Chat and multi-turn work. The application keeps the history and sends it every turn. |
| `ConverseStream` | Streamed events | Same as Converse | Interactive output. Streaming support is model dependent. |
| `InvokeModel` | One response, synchronous | Model-specific | Embeddings, image generation, native features outside Converse |
| `InvokeModelWithResponseStream` | Streamed | Model-specific | Native streaming. A different API, not a managed job. |
| `StartAsyncInvoke` | A managed asynchronous job | Model-specific `modelInput` | Long work written to S3. AWS describes it as used to generate videos. The model must support it. |

- **Permissions:** Converse uses `bedrock:InvokeModel`, and streaming uses `bedrock:InvokeModelWithResponseStream`. `StartAsyncInvoke` also requires `bedrock:InvokeModel`.
- **Streaming is not async:** streaming returns tokens sooner, but the application still holds the connection and compute until the response ends. Only `StartAsyncInvoke` hands the work to Bedrock.
- **Check model support:** before choosing Converse, streaming or async, check that the model supports that API.

## Sampling settings

Converse takes `temperature`, `topP`, `maxTokens` and `stopSequences` in `inferenceConfig`. `top_k` and other provider options go in `additionalModelRequestFields`. See [Sampling parameters](sampling-parameters.md) for what each one does and how to tune it.

## StartAsyncInvoke

| Part | Fields |
|---|---|
| Request | `modelId`, `modelInput`, `outputDataConfig` (required); `clientRequestToken` for idempotency and `tags` (optional) |
| Output location | `outputDataConfig.s3OutputDataConfig`: `s3Uri`, optional `kmsKeyId` and `bucketOwner` |
| Response | `invocationArn` |
| Follow-up | `GetAsyncInvoke` and `ListAsyncInvokes`; statuses `InProgress`, `Completed`, `Failed` |

The fields and follow-up calls come from the installed SDK model; the AWS page read for this does not describe the status calls.

## Where the request runs

Routing is a separate decision from the API. In-Region uses a model ID or ARN. A geographic inference profile routes within a geography such as US or EU. A global profile can route across supported commercial Regions worldwide. Pass a profile ID or ARN as `modelId`. Cross-Region routing does not guarantee lower latency. The [Inference profiles page](../labs.md) in the main app lists the profiles in your account.

## Go deeper

- Slides: [Pick the inference API](../decks/01-bedrock-inference.md#pick-the-inference-api), [Chat, one response, or a job?](../decks/01-bedrock-inference.md#chat-one-response-or-a-job), [Choose the routing boundary](../decks/01-bedrock-inference.md#choose-the-routing-boundary)
- Resilience: [Retry before the first visible chunk](../decks/09-resilience-and-routing.md#retry-before-the-first-visible-chunk), [Send each request to the right model](../decks/09-resilience-and-routing.md#send-each-request-to-the-right-model)
- Gotchas: [prompt routing is English-only](../gotchas.md#prompt-routing-is-english-only), [a router needs two models from one family](../gotchas.md#a-router-needs-two-models-from-one-family)
- Lab: the Converse Lab in [Labs and setup](../labs.md)

Sources: [Inference using the Invoke API](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-api.html), [StartAsyncInvoke](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_StartAsyncInvoke.html), [cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html).
