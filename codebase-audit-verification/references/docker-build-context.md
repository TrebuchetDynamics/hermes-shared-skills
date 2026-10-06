# Docker build context and `.dockerignore`

Applies to any repo whose image build reads an ignore file — for example a service subdirectory such as `service/` (see its `Dockerfile`, `docker-compose.yml`, `deploy/deploy-pi.sh`, `raspberrypi/build-arm64-image.sh`, `scripts/run-docker.sh`).

## Topology rules that cause silent breakage

- **`COPY` sources are relative to the context root.** Moving the context (repo root → subdirectory, or back) invalidates every `COPY` path and every ignore pattern at once. Drop the prefix consistently across `Dockerfile`, compose `build.context`, build scripts and the Makefile in the same change.
- **`.dockerignore` is read from the context root.** If the context is `service/`, the file must be `service/.dockerignore`. A workspace-root `.dockerignore` does nothing while the context is a subdirectory — check which file is actually live before crediting an ignore rule with anything.
- **Every build entry point must agree.** Enumerate them (`search_files` for `docker build`, `buildx build`, `build.context`) and confirm they pass the same context; one stale `cd ..` reintroduces the old behaviour on one path only.

## Pattern semantics that bite

- Patterns are **root-anchored**. `logs/` covers `<context>/logs/` but not `subdir/logs/`. Nested host-state directories need their own patterns.
- **Last match wins**, so a re-include (`!docs/`, `!docs/static.go`) survives only if nothing later re-excludes it. A trailing `**/*.md` therefore strips markdown everywhere, including inside re-included directories.
- **Directory-wide beats name-specific.** Excluding one key file by exact filename does not protect the next file added to that directory.
- A nested path can collide with a root-anchored pattern's name; verify the nested one still arrives.

## Probe: what does the context actually contain?

Cheaper than a build by orders of magnitude. Copy the real ignore file into a scratch dir, create **empty** files at the paths you care about, and let Docker report what it sent:

```bash
CTX=/tmp/ctx-probe && rm -rf "$CTX" && mkdir -p "$CTX"
cp service/.dockerignore "$CTX/.dockerignore"
cd "$CTX"
mkdir -p some/nested && : > some/nested/probe-file       # one stub per path of interest
printf 'FROM alpine:latest\nCOPY . /ctx/\nRUN for p in some/nested/probe-file; do [ -f "/ctx/$p" ] && echo "SENT     $p" || echo "FILTERED $p"; done\n' > Dockerfile
docker build --no-cache --progress=plain -f Dockerfile . 2>&1 | grep -E "SENT|FILTERED"
```

Check both directions:

1. Every `COPY` source in the Dockerfile must read `SENT`.
2. Host-only trees and key material must read `FILTERED`.

Build the stub list from real filesystem paths (a glob or `search_files(target='files')` against the tree), never by hand — a typo makes the pattern correctly fail to match and produces a false leak.

## Cheaper still: gate the real build on the cheapest stage

The probe above proves what the context *contains*. To prove the context is *usable*, build the smallest real thing that depends on it — never the production image:

```bash
docker buildx build --platform linux/amd64 --target <builder-stage> \
  --build-arg GIT_SHA=ctxverify --load -t <repo>-ctxverify:amd64 -f Dockerfile .
```

Targeting the compiler stage exercises `COPY <manifests>`, dependency resolution, `COPY . ./` and the compile — the parts a context or `COPY`-prefix change actually breaks — in minutes, while skipping any cross-arch/QEMU or vendored-C++ stages that dominate the full build. Use the **native** platform: the arm64 path is the slow one and adds no signal about context correctness.

**Read the artifact back out of the image; do not trust the build log.** Exit 0 means the layers were written, not that the thing runs:

```bash
docker run --rm --entrypoint sh <repo>-ctxverify:amd64 -c 'ls -la <output-path>; <output-path> --help'
```

Then remove the verify image and confirm no container was left behind. Finish by naming the stages the gate did **not** cover — those remain unproven until a real build or a deploy runs.

## The runtime stage must ship what the runtime resolves

A successful build proves the context reached the *builder*. It says nothing about what the final stage carries, and the runtime resolves paths at run time:

- **A file the runtime invokes or reads by relative path is a runtime dependency of the image.** When the server shells out to `tools/<name>.sh` or reads a document under `docs/`, that file must be `COPY`ed into the runtime stage and re-included in `.dockerignore` if a broad pattern drops it. Omitting it never fails the build — it fails, or silently degrades, on the first run.
- **A gate that degrades to a warning is worse than one that crashes.** The sharpest instance: a pre-transmission safety gate resolves its checker, cannot find it, and logs `check tool unavailable — starting anyway`. The documented contract is "fails closed on an expired authorisation"; the shipped image can never fail closed, because the checker is not in it — and an operator reads the warning as a pass. Grep the running container's logs for the fingerprint: a `no such file or directory` beside a `starting anyway` line, repeating once per cycle.
- **Guard the runtime `COPY` set, and derive the expectation.** A hand-typed list of required files rots the moment a dependency is added. The guards that hold are closure checks: derive what the runtime needs — a script's transitive relative-import closure, the relative paths the runtime shells out to — and fail when the runtime stage omits a member. Observed shapes: a static checker wired into the build's preflight, and a co-located test asserting every member of an entry script's relative-import closure appears in the runtime `COPY --from=build` set. Record the scan's boundary in the guard's own comment so a blind spot is not mistaken for coverage.
- **Read the artifact back before crediting the fix.** `docker run --rm --entrypoint sh <image> -c 'test -f <path> && echo PRESENT'` — neither the build log nor the `COPY` diff proves the file landed where the runtime looks for it.

## Paths worth re-probing whenever the ignore file changes

- **Vendored source and its caches**: `roskeys-imsi-catcher/` including `.git/`, `build/`, `cmake-build-*`; `srsRAN_4G/` build trees.
- **Host-only state that sits nested**, where root-anchored patterns miss it: `raspberrypi/logs/`, `raspberrypi/.pi-subagents/` (agent session transcripts), `raspberrypi/signing/`.
- **Required inputs that must survive**: `go.mod`/`go.sum`, `patches/`, `scripts/`, `cpp/`, `images/b210/`, `certs/`, `migrations/`, `internal/config/configs/`, `internal/carriers/data/plmn_world.csv`, `docs/static.go` + `docs/api/index.html` + `docs/swagger.{json,yaml}`, `configs/`.

The `internal/carriers/data/plmn_world.csv` case is the one to remember: its directory name collides with a root-anchored `data/` pattern, and it is `//go:embed`-ed — so losing it breaks the Go build rather than merely bloating the image. For any `//go:embed`'d path, confirm it survives the ignore rules before believing a build will work.
