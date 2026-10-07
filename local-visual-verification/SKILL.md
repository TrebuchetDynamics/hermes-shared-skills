---
name: local-visual-verification
description: "Use when verifying a UI change before claiming done."
version: 1.0.0
author: Hermes fleet agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ui, verification, browser, playwright, screenshots, secrets]
---

# Verifying a UI change by rendering it locally

A front-end change is unverified until something has drawn it and been looked at. A type-check, a green suite and a successful build prove it compiles, not that it reads. This is the order that gets a real render out of a locally-running app, and what to do when the app cannot render on this host at all.

## When to use

Load before claiming a front-end change is done — a new component, a restyle, a map or chart, a layout fix — and whenever the task is "make this page better" and no render exists yet.

## Procedure

1. **Establish that this host can render the page before planning the capture.** Read what the app's data comes from: a local database, a remote one, seeded fixtures. A dev server pointed at a remote production database will start, serve its login page, and then fail every query from inside your network — a 500 on login is usually a connection timeout, not a bad credential. Read the server's own log for the cause instead of guessing, then decide whether you are capturing the real page or a seeded fixture.
2. **Start the dev server as a trackable background job with a readiness signal**, not a foreground command: background it with a watch pattern matching the framework's own ready line, then confirm the port answers before capturing. Clear the port first — a fixture harness defaulting to the same port will fail to bind while your server holds it.
3. **Drive a browser that shares this host's network.** A remote or cloud browser resolves `127.0.0.1` to *its own* machine, so it cannot see your dev server whatever the URL says, and the failure looks like connection-refused on a page you know is up. For localhost, use the repo's own browser stack (its Playwright dependency, if it has one) or any local Chromium. When the installed Playwright's pinned browser revision is absent, do not re-download — point it at one that exists: `chromium.launch({ executablePath: '/usr/bin/chromium' })`, or a cached revision under `~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome`.
4. **Bind to the host name the server actually listens on.** A dev server that prints `localhost` may be bound to IPv6 only, so `127.0.0.1` is refused while `localhost` works. Try the other before touching the server.
5. **Authenticate the way the app authenticates, not by pattern-matching the URL.** A `TOKEN` in the environment is often a third-party provider key rather than the app's own session auth, and a `?token=` query that looks like a session is a common false lead. Find the app's login endpoint and POST to it, letting the browser context hold the cookie — one request then carries every later navigation.
6. **Capture the whole inspection round in one batch** — desktop and the compact class together, in a single script run: page-state probes (counts of the elements you added, plus what the fallback states say) and then the screenshots. Batching is what makes a single fix list possible.
7. **Judge at the size it ships, then fix everything the round shows in one batch and confirm at most once.** Look at the actual pixels, not the markup: an element that is legible enlarged can be an unreadable blur at its real size.
8. **Stop after the confirmation round.** Keep the harness in a scratch directory, kill the server, and confirm the port is free.

## Waydroid native app smoke

For a selected Waydroid test target, try `waydroid app install <qa.apk>` and
`waydroid app launch <qa-package>` before treating unauthorized ADB as preventing
all testing. The native platform service can install and launch without ADB.
Use an isolated QA package so the user's paired application is preserved.
Read back the installed package list and check the exact QA process after launch.
The CLI's install handler may ignore the platform installation return value, so
exit 0 alone does not prove installation or that the latest APK replaced an
existing copy. Establish installed-byte identity separately when claiming it.
A running process is launch evidence, not rendered UI, interaction, connection
or chat evidence. Headless Weston can refuse screen capture with `unauthorized`;
do not bypass compositor or Android debugging permission to get a screenshot.

## When the page cannot render here

Report the gap with its concrete cause rather than a partial claim, and verify the artifact a different way if you can:

- **Proof sheet.** Render the real artifact module — the actual exported function the app calls — over the real design tokens in a throwaway HTML file, at the size it ships and enlarged, on each surface it will land on. Screenshot it and look. This verifies the risky part (legibility, contrast, hierarchy of one component) with no app data and no auth, and it is worth saying plainly that it is not a page render.
- **Name what was not verified.** "It compiles, the suite is green, the artifact is proof-sheeted; the full page was not rendered because <cause>" is honest. Quoting a suite in place of a render is not.

## Pitfalls

- **A command carrying a credential in its arguments echoes it in its own error output.** A browser driver's failed-navigation log prints the full URL, `?token=...` included, into whatever captures stderr. Read secrets in-process so they never reach an argument list, and pipe commands that must take one through a redactor: `2>&1 | sed -E 's/token=[^ &"]*/token=<redacted>/g'`. If one does leak, say so unprompted and recommend rotating the value — a silently exposed key is worse than the failed capture.
- **An unreadable slot is worse than an absent one.** At the shipping size, a label that renders as a blur or a numeral that overruns its container damages the design more than leaving it out. Scale it to fit, move it somewhere it can be read (a tooltip, an accessible name), or drop it — then re-look at the new size to confirm rather than assuming the change worked.
- **Draw once and decode from the same source.** A legend restated by hand drifts from the thing it explains; build both from one exported entry list, so a drawing nobody can read cannot survive as its only definition.
- **State-telling must not depend on colour alone.** Anything conveying a distinction by hue — measured versus assigned, fresh versus stale — needs a shape, weight or fill difference too, so it survives greyscale, low vision, and a bad projector.
- **A screenshot proves what rendered, not what it means.** Read the probe values alongside the image: a page can look right while showing none of the elements you added, because it silently served a login wall.
- **Never leave the verification server running.** A stray dev server bound to a shared or production data source is a live side effect you introduced.
