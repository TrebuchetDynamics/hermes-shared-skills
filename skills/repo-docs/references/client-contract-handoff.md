# Client contract reconciliation and delivery

Use when replacing stale API documentation or preparing a contract for another application. This is a documentation workflow, not permission to change runtime behavior or access production secrets.

## 1. Establish the target

Read the owning service's instructions and manifest. Resolve the source identity with `git rev-parse HEAD` and inspect `git status --short`. Determine whether the client needs HTTP, WebSocket messages, or both. Preserve the existing contract layout and generation ownership.

Compare any source-pinned file with its declared inputs. For a supplied source excerpt, compare its bytes with `git show <revision>:<path>` before claiming same-revision provenance. When storing attachments as repository references, record the supplied and stored SHA-256 values separately. Keep source excerpts byte-identical; if a guide needs local-link adaptations, list those edits and do not call the stored guide an unchanged copy. Check adapted links from the stored file's directory, because relocation changes relative-path resolution. A package version or matching route list does not identify a deployed binary. Bind live qualification separately to the active deployment/image identity.

If embedded or publicly served documentation disagrees with local source, record both observations with their scope. Do not infer which binary is deployed from the documentation text alone. Correct documentation within scope; queue a source repair when changing embedded runtime HTML exceeds documentation authority.

## 2. Trace the connection and dispatcher

Read the authentication route, upgrade handler, request parser, response builders and live/replay dispatcher together. Use source relationships to answer:

- Which endpoint and protocol are intended? Which exact Origin policy and viewer authentication method apply? Is the deployed allowlist known or only the configuration mechanism?
- Does the connection start live delivery automatically? Is there an actual subscription message? Do replay selectors persist as live filters?
- Which request types, required fields, defaults and unknown-field rules exist? What normalization and duplicate checks apply?
- Which modes share limits and which have separate validation? Do not copy one mode's weighted budget to another without tracing the caller.

Keep credentials out of examples. Distinguish allowlisted loopback development Origins from production application Origins. An example service URL is not an allowlist entry.

## 3. Document every replay mode separately

For raw, batched and synchronized/paged modes, record required timestamps, alignment, inclusive/exclusive bounds, maximum request duration, page size, supported family selectors, completion type and completion timestamp meaning.

Trace post-completion behavior: socket closure, raw-live resubscription or synchronized continuation. Record whether an offline flag disables only buffering or the entire live connection. Explain source errors, missing completion, broadcast lag, buffer exhaustion and write timeouts. Require clients to rehydrate after incomplete replay rather than infer successful completion from the last row.

Document duplicate handling through actual natural keys; do not invent a resume cursor. Preserve financial wire types, null semantics and schema-specific removed fields. A dense/defaulted projection is not canonical observed data.

## 4. Reconcile history and evidence requirements

List measured UTC coverage and retention by asset/family only when an authorized inventory provides it. Distinguish empty valid history, missing data, unavailable family, unsupported feed and unverified availability. A request ceiling is not a retention window. Successful completion is not continuity proof.

Map consumer-required fields to producer and wire evidence. For market books, check market/window identity, both outcome tokens, stored ladder depth, source event identity/time, immutable collector first receipt, collector generation, gap/reset markers and positive unchanged-book continuity. Do not treat observed-at, venue-observed or silence as proof of those stronger properties.

Keep consumer receipt and state-ready times separate. Historical replay cannot retroactively qualify a decision. Missing producer evidence needs an implementation-plus-regression backlog slice, not merely stronger prose.

## 5. Verify and deliver

Check JSON syntax, internal references and unique operation IDs. Validate the full OpenAPI document separately when available; component-schema checks do not equal full OpenAPI validation. Verify guide links and reconcile examples with parser/builders. Run existing safe source-bound contract tests when useful, labeling static source checks separately from socket/runtime tests.

Deliver the requested artifact directly. Include the companion WebSocket guide when live/history clients need it. If exhaustive message schemas are not yet available, attach same-revision parser and payload-builder files and name the missing schema/live evidence. Never describe synthetic examples as captured redacted records. Avoid repeating a long status report when the user asked for a file.
