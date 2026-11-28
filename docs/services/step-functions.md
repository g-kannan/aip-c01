# AWS Step Functions

Step Functions builds workflows, called state machines, from steps called states. A running workflow is an execution. In a generative AI application it is the control plane around the calls that do the AI work: Bedrock, agents, and tools.

A scenario to hold in mind: two analyses run side by side, a risk threshold decides what happens next, tool calls sometimes fail for transient reasons, and an auditor needs the execution path afterwards.

## Map the scenario to states

| Need | Step Functions feature |
|---|---|
| Two analyses at the same time | A `Parallel` state runs each branch concurrently and waits for all of them. Its output is an array with one element per branch. |
| A risk threshold decides the path | A `Choice` state adds conditional rules. Set a `Default`, because with no matching rule and no `Default` the state machine throws an error. |
| Transient tool failures | A `Retry` rule on the state, with `IntervalSeconds`, `MaxAttempts`, `BackoffRate`, an optional `MaxDelaySeconds` and a `JitterStrategy` |
| A fallback when retries run out | A `Catch` rule with a `Next` state. Retriers are used first. |
| An auditable path | Standard workflows show execution history and visual debugging |

## Details worth knowing

- **Error default:** when a state reports an error, Step Functions fails the whole execution unless a `Retry` or `Catch` handles it. `Retry` and `Catch` apply to `Task`, `Parallel` and `Map` states.
- **Retry defaults:** `IntervalSeconds` is 1, `MaxAttempts` is 3, `BackoffRate` is 2.0, and `JitterStrategy` is `NONE`. Set `FULL` to randomize each wait. A `MaxAttempts` of 0 means never retry.
- **`Parallel` failure:** if one branch fails, the whole `Parallel` state fails and its other branches are stopped. Lambda functions already invoked continue to run.
- **Standard or Express:** Standard suits long-running, auditable workflows: up to a year, exactly-once, with execution history in Step Functions. Express suits high-event-rate work: up to five minutes, at-least-once, with history sent to CloudWatch Logs. For "durable and auditable", choose Standard.
- **Calling Bedrock:** there are optimized integrations for the Bedrock `InvokeModel` and `CreateModelCustomizationJob` APIs. For anything else, a Lambda task can call Bedrock APIs, invoke a Bedrock agent alias, or call a Strands-based agent runtime.

## Amazon Bedrock Flows

Bedrock Flows builds workflows by linking prompts, foundation models and other AWS services such as Lambda and knowledge bases. You build it visually, deploy it as an immutable version behind an alias, and call it with `InvokeFlow`.

Flows is stronger when the main requirement is prompt chaining, model calls and conditional GenAI composition. It is not the best match when operations teams need the workflow controls that state machines provide: durable orchestration, tuned retry policies, parallel branches and an auditable execution history. That boundary is design guidance; the AWS Flows page gives no "use Flows when" rule.

## Agent traces and router logs

Agent traces and custom router logs help developers understand what an agent did. They are observability, not orchestration, and do not replace a managed workflow service when the scenario depends on durable state, retry policies and an auditable execution path.

## Choosing an orchestrator

Work down the list and stop at the first fit.

1. **A few fixed steps, such as classify then answer:** a prompt chain in code.
2. **Prompt chaining and conditional composition, built visually and versioned:** Bedrock Flows.
3. **Durable orchestration with parallel branches, conditions, retries and execution history:** Step Functions, Standard workflows.
4. **The model must pick the steps and tools:** an agent. Wrap it in Step Functions when you still need durable state and retries.
5. **Understanding what an agent did:** agent traces and logs. Use them to debug, not to orchestrate.

| Option | Pick it because | Watch for |
|---|---|---|
| Prompt chain in code | Simplest thing that works | You own retries, state and audit |
| Bedrock Flows | Visual, versioned prompt graphs | Not a substitute for state-machine controls |
| Step Functions | Durable state, `Parallel`, `Choice`, `Retry`, history | More to design; Standard versus Express matters |
| Agent | The model chooses the steps | Less predictable; needs limits and monitoring |
| Traces and logs | Developers can see behaviour | No durable state, retry policy or managed audit path |

## Go deeper

- Slides: [When the workflow needs a control plane](../decks/12-prompt-governance.md#when-the-workflow-needs-a-control-plane), [Pick the orchestrator that fits](../decks/12-prompt-governance.md#pick-the-orchestrator-that-fits), [Retry the transient ones only](../decks/09-resilience-and-routing.md#retry-the-transient-ones-only), [Wait longer and randomly](../decks/09-resilience-and-routing.md#wait-longer-and-randomly), [Every loop needs an exit](../decks/09-resilience-and-routing.md#every-loop-needs-an-exit)
- Related: [Prompt management](../bedrock/prompt-management.md), [Other AWS services](index.md)

Sources: [What is Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html), [Handling errors](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html), [Parallel](https://docs.aws.amazon.com/step-functions/latest/dg/state-parallel.html), [Choice](https://docs.aws.amazon.com/step-functions/latest/dg/state-choice.html), [Bedrock integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrock.html), [Amazon Bedrock Flows](https://docs.aws.amazon.com/bedrock/latest/userguide/flows.html).
