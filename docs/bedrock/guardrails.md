# Guardrails

Amazon Bedrock Guardrails apply content policies to the text going into a model and the text coming out.

## Two ways to apply

| Mode | How | Use it when |
|---|---|---|
| Attached | Pass the guardrail identifier and version with `Converse` or `InvokeModel` | Input and output of a Bedrock call should both be checked |
| Standalone | `ApplyGuardrail` with `source` set to `INPUT` or `OUTPUT` | Checking any text with no model call: another provider, retrieved text, or testing a guardrail against samples |

Roll out in detect mode first (action `NONE` reports what each policy would do and changes nothing), measure false positives, then enforce.

## Sensitive information filters

| Topic | Fact |
|---|---|
| What they check | PII in input prompts and model responses |
| Actions | `BLOCK` the content, `ANONYMIZE` (mask with labels such as `{EMAIL}`), or `NONE` to detect only |
| How detection works | Probabilistic, ML-based and context-dependent. It works better with enough surrounding context. Custom regex filters match patterns instead, without lookaround. |
| Not evaluated | PII in tool call arguments (`toolUse.input`), tool results the application returns (`toolResult`), and tool definitions (`toolSpec`) |
| Originals remain | The `match` field in API responses and traces holds the original PII value. The `input` field in model invocation logs always holds the original request. |

For tool-calling applications, redact or tokenize sensitive values at the application boundary. Guardrails are not log redaction: AWS recommends CloudWatch log data protection for logs.

## Go deeper

- Slides: [Six policy types](../decks/06-guardrails-defense-in-depth.md#six-policy-types), [On the model call, or on its own](../decks/06-guardrails-defense-in-depth.md#on-the-model-call-or-on-its-own), [Detect first, enforce later](../decks/06-guardrails-defense-in-depth.md#detect-first-enforce-later), [Guardrails do not replace validation](../decks/06-guardrails-defense-in-depth.md#guardrails-do-not-replace-validation), [Guardrail PII filters have blind spots](../decks/07-privacy-and-governance.md#guardrail-pii-filters-have-blind-spots)
- Related: [Monitoring and logging](monitoring-and-logging.md), because invocation logs hold the unmasked request
- Lab: the Guardrails Lab in [Labs and setup](../labs.md)

Sources: [Sensitive information filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html), [ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html).
