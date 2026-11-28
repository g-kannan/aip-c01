# Sampling parameters: temperature, top_p, top_k

Sampling parameters decide how the model picks each next token from its probability distribution. They trade predictability against variety. This page covers what each one does, where it goes in a Bedrock request, and how to tune it without guessing.

The Converse field names and ranges below were checked against the installed botocore `bedrock-runtime` model. Model-specific behavior comes from the AWS page on inference request parameters, listed under Sources.

## What each one does

| Parameter | What it controls | Lower value | Higher value |
|---|---|---|---|
| `temperature` | How flat or sharp the token distribution is | More predictable, repeats the likeliest wording | More varied, more surprising wording |
| `topP` (nucleus) | Keeps the smallest set of tokens whose probabilities add up to P, drops the rest | Narrow pool of likely tokens | Wide pool, including low-probability tokens |
| `top_k` | Keeps only the K likeliest tokens | Narrow pool | Wide pool. It only helps when K was actually cutting off useful choices. |

Temperature reshapes the probabilities. `topP` and `top_k` cut the candidate pool. They interact, so changing several at once hides which one did the work.

## Where they go in a request

| Parameter | Converse | Notes |
|---|---|---|
| `temperature` | `inferenceConfig.temperature` | Float, 0 to 1 in the Converse model |
| `topP` | `inferenceConfig.topP` | Float, 0 to 1 |
| `maxTokens`, `stopSequences` | `inferenceConfig` | Not sampling, but set in the same place |
| `top_k` | `additionalModelRequestFields` | Not in the common `inferenceConfig`. The key name and range are set by the model provider. |

```python
bedrock.converse(
    modelId=model_id,
    messages=messages,
    inferenceConfig={"maxTokens": 400, "temperature": 0.7, "topP": 0.9},
    additionalModelRequestFields={"top_k": 250},   # key name is model-specific
)
```

Bedrock supports the common parameters across models, but **exact support and valid ranges vary by model**. A value that is valid for one provider can be rejected or ignored by another. Check the provider's page before you set one. With `InvokeModel`, every parameter goes in the model's own request body instead.

## Scenario: marketing copy keeps repeating itself

The setup: a model writes creative marketing text. Factual grounding and JSON validity already pass. The wording is repetitive. `top_p` is already moderately high and `top_k` is already broad.

1. **Ask what is limiting variety.** A moderately high `top_p` and a broad `top_k` already let the model consider many tokens. So neither is the likely cause, and widening them further would not add much.
2. **Raise temperature first, moderately.** It is the remaining control that makes the model choose less-likely tokens more often. Make the change small, such as 0.3 to 0.6, not a jump to the maximum.
3. **Keep the guardrails passing.** Factual grounding and JSON validity must still pass after the change. Higher temperature can break both, which is why the test must check them.
4. **Test, don't ship.** Run the old and new settings side by side on the same prompts and measure the difference.

| Wrong move | Why it fails |
|---|---|
| Raise `top_p` to the maximum | A very high `top_p` lets in low-probability tokens, which can hurt style consistency. The pool was already wide. |
| Raise `top_k` further | It helps only when `top_k` is the limit. It is already broad, so it is not. |
| Lower temperature to 0 | Gives the most repeatable output, the opposite of what is wanted. |
| Rewrite the prompt first | A valid option, but the scenario asks for the sampling control. Change one variable at a time. |
| Change all three at once | You cannot tell which one changed the outcome. |

## Change parameters through a controlled test

- Change **one** parameter per experiment and keep the prompts, model and data fixed.
- Run an **A/B test** on a fixed set of representative prompts, then measure against user and quality metrics: variety, brand tone, factual accuracy, JSON validity, and user engagement where you have it.
- Sampling is random, so run each prompt several times. One good sample proves nothing.
- Use **Amazon Bedrock model evaluation** to score outputs against task-specific criteria before wider rollout. See [deck 05](../decks/05-bedrock-evaluation-metrics.md) and [deck 11](../decks/11-evaluate-and-troubleshoot.md).
- Roll out gradually, and keep the old setting so you can roll back.

## Quick rules

| Goal | Direction |
|---|---|
| Extraction, JSON output, factual answers | Low temperature (0 to 0.3) |
| Creative or marketing text | Moderate temperature, then test |
| Output is too repetitive | Raise temperature a little first |
| Output is off-brand or incoherent | Lower temperature, or lower `topP` |
| Cut off rare strange tokens | Lower `topP` or `top_k` |

Do not set `top_k` and `topP` extremes together and expect predictable results. Move one control, measure, then move the next.

## Known limits

- I did not verify the `top_k` key name or range for any particular provider. It differs by model, so read that provider's section of the AWS page.
- The 0.3 to 0.6 range is a starting suggestion for a first test, not an AWS figure.
- Some newer models restrict which sampling parameters you can set together or at all. Re-check the model's page before you rely on a combination.

## Go deeper

- Lab: the Converse Lab slider in [Labs and setup](../labs.md) changes `temperature`. It does not expose `topP` or `top_k`.
- Slides: [Converse parameters](../decks/01-bedrock-inference.md#pick-the-inference-api) in deck 01.

Sources: [Inference request parameters and response fields for foundation models](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters.html), [InferenceConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InferenceConfiguration.html), [Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html), [Evaluate model performance](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation.html).
