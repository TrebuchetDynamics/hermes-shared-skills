## Scratch hygiene

Keep per-card scratch (build outputs, copies, logs, probes) inside the repository's ignored
folders or under `~/.hermes/cache/scratch/<card-id>/`, never as new top-level folders in
`~/.cache`. Prefer the project's normal build directory over a private `CARGO_TARGET_DIR`
or copy of the repo. Before finishing a card, delete the large build outputs you created
(`target/`, `build/`, copied repos) and keep only the evidence the handoff cites. A weekly job
deletes worker scratch older than 7 days.
