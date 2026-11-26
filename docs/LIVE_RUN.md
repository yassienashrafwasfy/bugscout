# Live Claude Code run (2026-11-26)

A real, non-interactive Claude Code session (`claude -p`, v2.1.332, model `claude-sonnet-5-5`) was connected to the BugScout stdio server
and told to follow the `testing_loop` prompt against `examples/sample_api`. Only the `bugscout` MCP tools were allowed (Bash, Edit and
Write were disallowed). The system prompt supplied the charter and said that no human was available
(see [`scripts/live_run_system_prompt.txt`](../scripts/live_run_system_prompt.txt)).

```bash
claude -p "/mcp__bugscout__testing_loop" --mcp-config live_mcp.json --strict-mcp-config \
  --allowedTools "mcp__bugscout" --disallowedTools Bash Edit Write \
  --append-system-prompt "$(cat scripts/live_run_system_prompt.txt)" --max-budget-usd 6
```

**Result:** 35 turns, 34 tool calls, 68 s, about $0.22. The agent mapped the API (`import_openapi`), ran the six static tools, ran
schemathesis, probed by hand with `http_request`, recorded bugs, read the report and ended the run. It did not answer or approve either escalation.

| Bug the server reported | Oracle | Occurrences |
|---|---|---|
| `GET /items/{item_id}` returns 500 for negative ids | crash | 5 |
| `GET /orders/{order_id}` response lacks the required `total` | schema | 135 |

**What the run exposed (and what was done):**

* `add_test_idea` on `GET /items/{item_id}` was escalated as out of scope although the charter included `/items/*`: the scope guard matched an endpoint
  key as if it were a Python target. **Fixed** in `guards/scope.py`, with a unit test.
* The first two `record_bug` calls omitted `kind` in the repro; the server rejected them as unsupported and marked the manual nodes flaky. The agent
  re-recorded them correctly. The behaviour is as designed; the tool description could be clearer.
* `DELETE /items/{item_id}` was held back by the destructive guard and left as a pending escalation, so that endpoint was not tested.

**Limits of this evidence:** one run, one example (`sample_api`), one model. The `sample_lib` example and the Codex client have not been driven by a live agent.
The sample_api's planted bugs are the 500 on negative ids and the schema mismatch; both were found.
