# Model configuration interface

A new API model joins the standard agent track by swapping one JSON file: the simulator adapter,
prompt, tool schema, controller and budgets stay as they are. Copy the template that matches the
provider's interface, set the model identifier and the key file, and start the bridge.

```bash
export AGENT_RUNTIME_DIR="$PWD/configs/private/agent"     # private, mode 700, not in git
mkdir -p "$AGENT_RUNTIME_DIR"
cp configs/model_configs/responses.example.json "$AGENT_RUNTIME_DIR/provider.json"
# edit base_url / model / reasoning_effort / max_output_tokens, then:
printf '%s' "$YOUR_KEY" > "$AGENT_RUNTIME_DIR/api_key"; chmod 600 "$AGENT_RUNTIME_DIR/api_key"

python3 -m policy.GPT6.local_bridge --config "$AGENT_RUNTIME_DIR/provider.json" \
  --token-file "$AGENT_RUNTIME_DIR/bridge.token" --log-dir "$AGENT_RUNTIME_DIR/logs" \
  --port 18770 --max-calls 120
```

`--max-calls 120` is required: the standalone bridge defaults to 40, while the evaluated
configuration is 120 calls per episode. See [docs/EXTERNAL_AGENT.md](../../docs/EXTERNAL_AGENT.md)
for the budget ledger, the token file and the simulator-side variables
(`AUTO_LAUNCH=0`, `PORT`, `GPT6_BRIDGE_TOKEN_FILE`).

| Key | Meaning |
| --- | --- |
| `provider` | `responses`, `chat`, `anthropic` or `gemini`; selects the transport and history format |
| `base_url` | HTTPS API base, no query or credentials. Gemini takes the API base; the bridge appends `/v1beta/models/<model>:generateContent` |
| `model` | exact provider model identifier, as it will appear in the submission |
| `reasoning_effort` | sent as `reasoning.effort`, `reasoning_effort`, `output_config.effort` or `thinkingConfig.thinkingLevel` depending on the provider |
| `max_output_tokens` | output cap per request. Optional; the provider default is used when absent |
| `api_key_file` | path to a file containing only the key. Never inline the key |

Nothing in this directory may contain a real key, endpoint credential or private seed list. The
files here are templates; put the filled copy in `AGENT_RUNTIME_DIR`, which is outside version
control.

A model whose reasoning can consume the whole output cap before it emits a tool call needs a larger
`max_output_tokens`; report the value you used, because it changes the result.
