
## Hermes fleet rules (local overlay; overrides conflicting text above)

These rules come from the Hermes fleet, not upstream. `extras/impeccable/sync_impeccable.sh` in the shared skills repo
re-appends them after every upstream sync. Where they conflict with anything above, they win.

1. **Route by intent, never to dodge `init`.** A request to match, port or look like a named
   product ("Hermes Desktop UI/UX in our app", "make it look like Linear") is a *redesign toward
   a reference*. Run `init` (PRODUCT.md), then `new-work` with that reference as the pinned brief.
   The brief wins, so the reference's visual language is the target world. Never downgrade such a
   request to `polish` or another refinement mode just because PRODUCT.md is missing. Polish is
   only for "keep our look, make it better".
2. **Ask, don't block.**
   - In a live session, ask the `init` interview and the direction round through `clarify`: one
     call, at most 5 questions, the recommended or assigned choice first.
   - Without a live answer mechanism (cron, kanban worker, delivered report), do not stop:
     - `init` infers from the explicit brief and repository evidence and labels its assumptions,
       as init.md allows.
     - The direction round builds the direction that `concept-seed` assigned.
     - Then report the alternatives as a numbered questionnaire ("Reply e.g. 1A; no reply = the
       built direction stands").
   - Never end a turn with "the build starts when you pick". Visual direction is reversible, so
     build the recommended one and let the owner switch.
3. **Delegation carries the skill.** If implementation is handed to `delegate_task` or a worker,
   the brief must name:
   - the chosen mode and playbook;
   - the reference files to load with `skill_view impeccable <file>` (always
     `reference/craft-floor.md`);
   - the pinned brief or reference;
   - the bounded verification rounds (desktop and compact captures).
   On return, the parent runs the detector (`scripts/impeccable detect <changed paths>`) and
   compares against the brief before reporting.
4. **Impeccable artifacts are project files.** PRODUCT.md, DESIGN.md (and its sidecar) and
   `.impeccable/` (config, surface briefs, decision records) belong in the repository. When
   shipping the work (`git-commit-push`), commit them with it unless the user said otherwise.
   Mocks and screenshots under `.impeccable/mocks/` or task evidence folders follow the repo's
   gitignore.
