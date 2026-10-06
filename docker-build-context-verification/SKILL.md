---
name: docker-build-context-verification
description: "Verify Docker build-context and .dockerignore changes."
version: 1.0.0
author: SDRHF Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [docker, dockerignore, buildkit, build-context, verification]
---

# Verifying a Docker build-context change

Moving a build context, rewriting `COPY` prefixes, or editing `.dockerignore` all fail **only at build time** — which is usually deploy time, the worst place to find out. Two cheap gates answer the real questions without paying for a full image build.

## When to Use

Load this whenever a change touches a `Dockerfile`, its build context, or a `.dockerignore` — especially before recommending the change be committed.

## The two questions

1. Does the context still contain every path the `Dockerfile` COPYs?
2. Does `.dockerignore` exclude what it claims (and not more)?

## Gate 1 — stub-context `.dockerignore` test (~10 s)

Docker resolves ignore patterns against the **build-context root**, so a temp dir holding the *real* `.dockerignore` plus empty placeholder files at the exact paths of interest reproduces the semantics exactly:

```bash
CTX=$(mktemp -d); cp <ctx-root>/.dockerignore "$CTX/.dockerignore"; cd "$CTX"
# empty files at every COPY source AND at paths that must be excluded
mkdir -p patches images/b210 internal/server docs/api
: > go.mod; : > patches/x.patch; : > images/b210/b210_fpga.bin
: > internal/server/server.go; : > internal/server/server_test.go
: > docs/static.go; : > docs/README.md
printf 'FROM alpine:latest\nCOPY . /ctx/\nRUN find /ctx -type f | sed "s|^/ctx/||" | sort\n' > Dockerfile
docker build --no-cache --progress=plain -f Dockerfile . 2>&1 | sed -n '/RUN find/,$p'
```

Build the path list from the **real filesystem** (`ls -d prefix*/`), never by hand-typing directory names: a one-character typo in a stub path yields a confident, wrong "this pattern does not work" answer. To assert a specific expectation, replace the `find` with a `for p in …; do [ -f "/ctx/$p" ] && echo SENT || echo FILTERED; done` loop.

Two semantics worth knowing, both confirmed by this harness:

- A root-anchored `data/` does **not** match `nested/data/file.csv` — so `go:embed` targets under a nested dir survive the ignore file.
- `foo/.git/` does exclude `foo/.git/HEAD`.

## Gate 2 — build one stage natively (~1–2 min)

```bash
docker buildx build --platform linux/amd64 --target <builder-stage> --load -t probe:amd64 -f Dockerfile .
```

Targeting the compile stage proves the context and ignore file feed a **compiling** build, without the cross-platform emulation cost of a full multi-stage image. Find stage names with `grep -nE '^FROM' Dockerfile`. Then read the artefact back out rather than trusting the log:

```bash
docker run --rm --entrypoint sh probe:amd64 -c 'ls -la /path/to/output'
docker rmi probe:amd64
```

Clean up your own probe image and check for a leftover container (`docker ps --filter ancestor=probe:amd64`) so the verification leaves nothing behind.

## Gate 3 — boot-check the built image in the container's real privilege shape

The cheapest real proof that the runtime stage is correct is to run it and execute the payload it ships:

```bash
docker run --rm --user 0:0 --cap-add=NET_ADMIN --cap-add=SYS_NICE \
  --entrypoint /bin/sh <image> -c '/path/to/payload --help; /path/to/server --help'
```

Match the **user, capabilities and environment the real container runs with** — read them from the compose file and from `docker exec <container> env`. Do **not** use host networking: a probe that binds the production port collides with a live service. Two probe artefacts look exactly like broken images and are not:

- a `setcap`-marked binary fails with `Operation not permitted` when its file capabilities are absent from the container's bounding set;
- the same binary exec'd by a **non-root** user enters secure-exec, drops `LD_LIBRARY_PATH`, and reports `cannot open shared object file` for a library that is demonstrably present. Running as the user the container actually uses resolves it.

Establish which of these you are looking at before reporting a defect.

## What these gates do NOT prove

Other stages (native-library builders, runtime layers), the cross-architecture compile path, asset/config `COPY`s into the runtime image, whether the image behaves correctly once deployed, or an actual deploy. Gate 3 proves the runtime image boots and its payload executes; it does not prove the end-to-end field path. Say that explicitly; "the Go stage builds" is not "the image works".

## Pitfalls

- **Mirror every entry point that hardcodes the context.** A context move is never one line: the Dockerfile, `docker-compose.yml` `build.context`, the Make target, deploy scripts, and any image-builder helper each carry the old root. Grep for the old prefix (`-f <dir>/Dockerfile`, `context: ..`) rather than trusting memory.
- **A guard script edited alongside the thing it guards validates the working tree, not the commit.** If a checker's expected literals were updated in the same diff as the paths it checks, say which one the PASS refers to. Cheapest way to test its substance without an image build: lift the checker's individual `grep -Fqx '<literal>'` / `grep -Fq '<literal>'` assertions out and run them against the real files yourself.
- **Check the ignore file is TRACKED (`git ls-files`).** An untracked `.dockerignore` protects exactly one machine — every fresh clone builds with no exclusions at all. Establish the *previous* exclusion state from git rather than the working tree: `git show HEAD:<dockerignore>` and `git show HEAD:<compose-file>` show what the committed state actually did, independent of local edits. A key present on disk but absent from every tracked ignore rule was going to the daemon on every build.
- **A relative `context:` in a compose file resolves against the compose file's directory, not the shell's cwd.** `context: .` in `service/docker-compose.yml` means `service/`, so the ignore file Docker reads is `service/.dockerignore`. Resolve this before reasoning about which ignore file is active — getting it wrong sends you analysing an inert file.
- **A `.dockerignore` only applies from the context root.** If a context change moves the root, the ignore file's location must move with it — and the old root may have had none at all, meaning the previous builds shipped everything (`.git`, `data/`, `.env`) as context.
- **Directory exclusions can be filename-specific.** A pattern naming one file (a signing key) does not protect a second key added later to the same directory — prefer excluding the directory and re-including the public members.
- **`--provenance=true` cannot be combined with `--load`.** The `docker` driver answers `Attestation is not supported for the docker driver`; the `docker-container` driver answers `docker exporter does not currently support exporting manifest lists`. A local `--load` build can therefore never carry attestations — they require `--push` to a registry (or an OCI output). Check whether an existing repo build target makes this mistake before concluding the failure is your change.
- **Reuse the repo's own image-builder script.** A hand-rolled `buildx` invocation tends to omit four things at once: the revision build-arg, the intended tags, the intended builder, and retry-on-failure. Read the script and call it instead of re-deriving its flags.
- **A build that is not advancing is not necessarily slow.** If the progress log's mtime has stalled *and* no compiler processes exist (`pgrep -xc cc1plus`, `ninja`) while the CLI still waits, the daemon-side worker is gone — kill the CLI rather than waiting. A wedged build sends no completion notification, so silence past the expected window is a signal, not patience.
- **Prune BuildKit cache, never "reclaimable" volumes, to free space.** `docker builder prune -f` discards only regenerable cache. The volume "reclaimable" figure in `docker system df` can be other projects' live data — a Postgres data directory, multi-GB datasets — so enumerate with `docker system df -v` and identify each volume before deleting anything.
- **`pgrep -f '<pattern>'` matches your own shell** whenever the pattern text appears in the command being run, so a filter or kill script can terminate itself mid-run and its own output becomes meaningless. Match the executable name (`pgrep -x`, `/proc/<pid>/comm`) and read `/proc/<pid>/cmdline` before killing anything.
- **Never sum `docker images --format '{{.Size}}'`.** Those strings mix units (`379MB` beside `1.09GB`), so arithmetic over them produces confident nonsense. Take totals from `docker system df`.
- **A tag is not the running container.** Building re-points tags, so inspecting a tag after a build says nothing about what is deployed; compare `docker inspect <container> --format '{{.Image}}'` against the candidate image ID. A bare image SHA is also not a valid `docker run` reference — tag it first.
- **A compose service's `image:` may be a tag another pipeline stages from.** `docker compose build` and `up --build` tag their result with the service's own `image:` value, so a local convenience rebuild silently overwrites a shared artefact — a burn, staging or publish step that consumes that tag. Compose can interpolate it (`image: app:${TAG:-latest}`), so pass a distinct tag for local builds instead of letting a convenience target re-point the shared one, and check what a repo's existing build script is allowed to overwrite before running it.
- **Check what the host already runs before starting a heavy build.** An emulated cross-architecture compile occupies every core and can exhaust swap; if a live service shares the box, establish its state first and prefer an idle window — and if that service runs in discrete phases, act in the gap between them rather than mid-phase, because a restart or a resource spike there can cost a whole cycle. Check before starting, not after being asked.
- **Architecture comes from the image, never from the tag name.** A tag that names an architecture (`:latest-arm64`) is a label someone chose; `docker inspect <image> --format '{{.Os}}/{{.Architecture}}'` is the fact. On an x86_64 host an image tagged `-arm64` is routinely amd64, and a fresh arm64 build will run under QEMU — so "deploy the image I just built" can downgrade a timing-sensitive service to emulation. Verify architecture for the candidate image *and* the running container before recommending a swap, and build for the host's own architecture when the service is local.
- **The OCI revision label is the traceability gate — confirm it after building.** Any build path that does not pass the revision build-arg writes `revision=unknown`, which downstream burn/verify tooling is entitled to reject outright. Repo build helpers export it; an ad-hoc `docker compose build`, or any wrapper that spawns compose in a subprocess without exporting it, does not. Check `docker inspect <image> --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'` before calling an image deployable, and prefer a build path that stamps a real revision.
- **After deploying, verify the service's workload, not the container's health.** `health=healthy` only means the supervisor is satisfied; it can be true while the main payload has not started. Confirm the actual process is running (`docker exec <container> sh -c 'pgrep -c <process>'`) and, for a service with phases, that it reached a working phase — then say which of the two you checked.
- **Read what a rollout wrapper actually executes before planning around it.** A target named `rebuild`/`deploy`/`up` may *rebuild from source* (`docker compose up -d --build`) rather than deploy the artefact you just verified, and it carries its own tag, platform and revision-arg defaults — so it can both discard your verified image and re-point a shared tag. Read its command (`--help`, or the function it calls) and decide whether you are deploying an artefact or triggering a fresh build; when it is the latter, deploy the staged image directly instead (`RIG_VIGIA_IMAGE_TAG=<sha>-<arch> docker compose up -d`).
