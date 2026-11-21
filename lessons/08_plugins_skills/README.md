# Lesson 08 — Plugins and skills

## In simple words

- A **hook** (lesson 07) is one behaviour.
- A **plugin** is a box of behaviours that belong together: hooks + tools + setup code + state.
  You add the box to any agent with one line: `Agent(plugins=[TokenBudget(...)])`.
- A **skill** is a plugin that gives the agent **instructions on demand**. Each skill is a folder with a
  `SKILL.md`. The agent first sees only the names and one-line descriptions. When a request needs a skill,
  the model loads its full instructions with the `skills` tool.

Why skills matter: an agent that supports 20 workflows should not carry 20 sets of instructions in every
request. That wastes tokens and confuses the model. Skills keep the context small until a workflow is needed
("progressive disclosure", a form of context engineering).

Strands ships these plugins: `AgentSkills`, `GoalLoop`, `ContextInjector` (lesson 10), `ContextOffloader`,
steering handlers (lesson 09), Todos, and `MultiAgentPlugin` for graphs/swarms.

## Files

| File | What it shows |
|------|---------------|
| [skills/](skills) | Two skills: `refund-processing`, `order-tracking`. |
| [skills_agent.py](skills_agent.py) | A support agent with the shop tools + `AgentSkills`. |
| [goal_loop.py](goal_loop.py) | `GoalLoop` with a Python validator: retry until the answer is valid JSON with the right keys. |
| [custom_plugin.py](custom_plugin.py) | `TokenBudget`: your own plugin with two hooks, one tool and state. |

## A `SKILL.md`

```markdown
---
name: refund-processing            # lowercase-with-dashes, max 64 chars
description: Step-by-step procedure for refunding... Use when a customer asks for their money back.
allowed-tools: lookup_customer get_order_history process_refund   # optional
metadata:                          # optional, free-form
  owner: support-team
---
# Refund processing
1. Identify the customer ...
```

Optional sub-folders `scripts/`, `references/`, `assets/` are listed for the model when the skill loads.
The **description is the trigger**: write what the skill does and *when to use it*.

## `AgentSkills` settings

| Setting | What it does | Default |
|---------|--------------|---------|
| `skills` | Folder of skill folders, one skill folder, `Skill` objects, or `https://` URLs. | required |
| `strict` | Raise on a broken `SKILL.md` instead of skipping it. | `False` → use `True` in production so a bad deploy fails fast. |
| `max_resource_files` | How many resource files to list per skill. | 20 |
| `state_key` | Where activated skills are recorded in `agent.state`. | `"agent_skills"` |

## `GoalLoop` settings

| Setting | What it does | Default | Production advice |
|---------|--------------|---------|-------------------|
| `goal` | A function `(response, agent) -> bool \| {"passed", "feedback"}` (sync or async), **or** a sentence judged by a model. | required | Prefer functions: real checks (tests, JSON schema, links work). |
| `judge` | Model/prompt for sentence goals. | agent's model | Use a different/cheaper model. |
| `max_attempts` | Tries before giving up. | unlimited | **Always set it.** |
| `timeout` | Seconds for the whole goal run. | unlimited | **Always set it.** |
| `preserve_context` | Keep failed attempts in history. | `True` | `False` to save tokens if old attempts don't help. |
| `resume_prompt_template` | How feedback is phrased to the model. | built-in | Customize for your domain. |

## Writing a plugin

```python
class TokenBudget(Plugin):
    name = "token-budget"  # required, stable

    def __init__(self, max_tokens):
        super().__init__()
        self.max_tokens = max_tokens

    def init_agent(self, agent): ...  # optional one-time setup
    @hook
    def refuse_when_spent(self, event: BeforeInvocationEvent): ...  # event type from the hint
    @tool(context=True)
    def remaining_token_budget(self, tool_context: ToolContext) -> str: ...
```

`super().__init__()` collects every `@hook` and `@tool` method. Plugins are the unit a platform team shares:
"every agent in the company gets `CompanyAudit()` and `TokenBudget()`".

## Production notes

- **Skills are code.** Review them like code, version them (`metadata.version`), and test that the agent picks
  the right skill (lesson 18 has a `SkillSelectionAccuracyEvaluator`).
- **Skills guide; they don't enforce.** The model may still skip a step. Enforce must-follow rules with
  steering/interventions (lesson 09) or inside the tool.
- **Bound every loop.** `GoalLoop` without `max_attempts`/`timeout` can run (and bill) forever.
- **Plugins should be small and independent**, with a stable `name`, so teams can mix them.
- Loading skills from URLs pulls instructions from outside your repo: pin and review them.

## Try it

1. Add a third skill `account-troubleshooting` and ask a login question.
2. Make `valid_bug_report` also require `"platform"`, and watch how many attempts the model needs.
3. Add an `@hook` on `AfterToolCallEvent` to `TokenBudget` that counts tool calls into `agent.state`.
