# Optional external EEF agent

The `eef_bridge` registration reuses the legacy `policy/GPT6` adapter name. It is provider-neutral
at the transport boundary. No commercial-provider implementation, API key, gateway, or proprietary
bridge is included. This optional integration is not a ready-to-run named-model baseline.

Run an authenticated HTTP bridge on loopback and set `AUTO_LAUNCH=0`, `PORT`, and
`GPT6_BRIDGE_TOKEN_FILE` in private configuration. The token file is read by the adapter and sent
as a Bearer authorization header. Keep it outside tracked files. The adapter only accepts loopback
HTTP origins and disables HTTP redirects.

The bridge must accept `POST /reset` and `POST /infer`, both returning JSON with HTTP 200.
Infer input contains `instruction`, base64 PNG `images` for head/left/right cameras, `eef_state`,
`joint_state`, `feedback`, `contact_feedback`, and `step`. See the adapter for exact field semantics.
Infer output is one of:

- `{"type":"finish","note":"..."}`
- `{"type":"rejected","note":"..."}`
- `{"type":"move_eef","arm":"left","position":[0,0,0],"quaternion_wxyz":[1,0,0,0],"gripper":1}`

The last example describes the schema only, not a safe target for a particular scene.
Commands are checked and bounded before execution. Optional `api_seconds` and `usage` fields are
recorded for timing. The adapter has per-episode model-call and wall-time budgets; report them
separately from action-policy step budgets. Audit and wall-clock files are written next to the token
file, so place it in a private writable directory outside the source tree.
