# API-driven EEF agent

The `eef_bridge` registration uses `policy/GPT6` for a provider-neutral simulator adapter.
The repository now includes `local_bridge.py`, `motion_limits.py` and a portable budget ledger
implementation. Credentials, personal ledgers, provider accounts and campaign logs are excluded.
The bridge preserves the supplied experiment prompt, tool schema, history construction and action
bounds. Provider-specific compatibility modes are retained because they affect model inputs.
This migration is not evidence that every provider or checkpoint has been evaluated.

## Private configuration

Run the bridge from the repository root on a credential-holding machine. Create a private writable
runtime directory and set `AGENT_RUNTIME_DIR` to it. Keep it outside version control; `configs/private/`
is ignored. Use restrictive permissions (directory 700, credential/config files 600).

Supply a JSON config with `provider` (`responses`, `gemini`, `chat` or `anthropic`), `base_url`
(an HTTPS API base), `model`, `reasoning_effort` and `api_key_file`. The key file contains one line.
No provider URL or account is preconfigured. The bridge disables redirects and environment proxies.

Create these two files in `AGENT_RUNTIME_DIR` before the first run:

- `budget_config.json`: `{"models": {"YOUR_MODEL": {"context": 1000000, "output": 65536, "input_rate": 0.001, "output_rate": 0.001}}}`.
  Values here illustrate the schema only. Set verified maximum input/output tokens and conservative
  USD-per-token bounds for the chosen endpoint, including cache-related charges where applicable.
- `budget_ledger.json`: `{"cap_usd": 1, "prior_committed_upper_usd": 0, "requests": {}}`.
  Set your actual spending cap and prior spending. Never overwrite an existing ledger to restart a
  stopped campaign. The example cap deliberately cannot cover the example reservation.

Each request attempt reserves its maximum configured cost under a file lock before sending.
Failed or unknown requests retain their reservations. Supported usage records reduce the retained
amount after a response. Missing or invalid configuration fails closed. A budget or quota stop
requires reviewing private state before resuming; no historical account balance is shipped.
The budget bound is only conservative if the operator's token and pricing bounds are valid.

## Launch and transport

```bash
export AGENT_RUNTIME_DIR="$PWD/configs/private/agent"
python3 -m policy.GPT6.local_bridge \
  --config configs/private/provider.json \
  --token-file "$AGENT_RUNTIME_DIR/bridge.token" \
  --log-dir "$AGENT_RUNTIME_DIR/logs" \
  --port 18770 --max-calls 120
```

The token file must not exist at startup; it is created with mode 600 and is distinct from the API
key. Set `AUTO_LAUNCH=0`, `PORT=18770` and `GPT6_BRIDGE_TOKEN_FILE` for the simulator-side runner.
If the simulator runs elsewhere, forward the loopback port through SSH and securely provide the
same bridge token to that machine. Never forward the API key. The adapter accepts only loopback
HTTP origins and sends the token in the authorization header.

The bridge accepts `POST /reset` and `POST /infer`. Reset clears per-episode history and call count.
Infer receives instruction, head/left/right RGB images, measured EEF/joint state, execution/contact
feedback and step number. It returns `move_eef`, `rejected` or `finish`. The model gets no privileged
object poses. Its finish statement does not determine simulator success.

`move_eef` includes arm, absolute position, quaternion in wxyz order, gripper aperture, phase and
note. Phase-dependent translation/rotation bounds are defined in `motion_limits.py`; the simulator
adapter applies execution-side checks and segmented motion. Gripper-only commands retain the
measured pose. Other phases retain the gripper command. Model-call envelopes and internal controller
tracking thresholds are separate quantities.

The adapter configuration permits 120 model calls per episode and its wall budget is 3300 seconds.
The standalone bridge defaults to 40 calls unless overridden: use the explicit 120-call option
above to match the adapter setting. Record both budgets, API retry count and provider configuration.
A replay option is provided for saved-action diagnostics, not as an evaluated agent result.
Audit/video files are written beside the simulator-side token; use a private writable directory.

## Migration scope

Only source modules were migrated. The campaign-specific hardcoded account ledger was replaced
with explicit private configuration, an unreachable duplicate HTTP-error handler was removed,
and quota handling uses HTTP status/structured provider codes. These affect deployment/error
handling; the prompt, tool schema and model-level motion bounds are preserved. CPU tests mock
provider responses; they do not certify live API or GPU simulation behavior.
