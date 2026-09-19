# Dependency policy

- `dev.txt`: CPU-only repository validation and tests.
- `sim.txt`: inherited Python 3.10 simulation constraints, supplemented with `client.txt`.
- `client.txt`: HTTP, image and websocket client dependencies.
- `infer-dm05.txt`: directs users to the upstream backend's environment specification.

Each model backend uses its own upstream environment. Do not combine all model requirements
into a single environment or import private editable packages. See `docs/INSTALLATION.md` and
`docs/BACKENDS.md`. A complete cross-hardware dependency lock has not been validated.
