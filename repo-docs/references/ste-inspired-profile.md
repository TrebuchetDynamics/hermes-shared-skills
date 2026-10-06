# STE-inspired language profile

## Scope and authority

Apply this profile by default to new and changed English technical prose in an authorized repo-docs task. It is an STE-inspired project policy, not an official ASD mode or a claim of full compliance. Repository instructions, accepted requirements, technical accuracy, operational safety, and literal preservation take priority over style. Do not translate other languages or rewrite unrelated documents without authorization.

Repo-docs controls documentation ownership, truth, status, and lifecycle. This profile controls how supported facts are expressed. Neither replaces the other. A short, direct instruction can still be wrong or unsafe.

The reference edition is ASD-STE100 Issue 9, dated 2025-01-15. The official standard and governed project terminology are necessary for strict conformance work. This reference is a workflow summary, not the rulebook or dictionary. Do not use an unofficial word list or remembered rule as proof of compliance.

## Write from evidence

Identify the actor, action, object, condition, sequence, expected result, and recovery limits from actual requirements or implementation. Do not invent a service, database check, variable, command, prerequisite, actor, supported rollback, or PASS result to make prose clearer. If the intended meaning is unresolved, report the ambiguity and retain the original claim until evidence or an owner decision resolves it.

Prefer an explicit known actor. If the actor is unknown in a description, passive voice can be appropriate. Do not turn an unknown actor into a fabricated CLI, server, or operator. Put an important condition before its action when that improves execution clarity. Do not add extra steps that the interface does not support.

Use direct commands in procedures. Normally put one instruction in each sentence. Preserve simultaneous actions as simultaneous actions, not as an invented sequence. Present prerequisites before the dependent step. Give the actual observable result and the documented failure/recovery limit. Notes provide information, not concealed instructions. Preserve the repository's hazard classification and consequences. Do not invent an injury, data-loss, or damage risk to create a warning.

## Vocabulary and sentence structure

Use the repository's established terms consistently. Consult its glossary and schemas before selecting a preferred term. A worker, agent, executor, job, task, request, and goal can represent different concepts. Do not flatten those concepts or impose illustrative preferred terms from another project. Likewise preserve authentication versus authorization, concurrency versus parallelism, backup versus replica, and deployment versus release.

Keep necessary technical nouns and verbs, such as webhook, repository, and access token. Explain unfamiliar terms where useful. A glossary records domain meanings and permitted uses. It is not an exemption list for arbitrary prose, and a glossary term is not automatically an approved general STE word.

Prefer short, complete sentences and simple verb constructions. Use 20 words as a review target for procedural instructions and 25 for descriptions. Keep descriptive paragraphs on one topic, normally no more than six sentences. These targets do not establish compliance: formal STE counting treats some identifiers, measurements, hyphenated expressions, and parenthetical text specially. Ordinary whitespace counts are only approximate flags.

Untangle ambiguous noun groups. Normally keep general multi-word nouns to three words. Preserve an exact long technical name or identifier and explain it instead of changing its meaning. Use lists when necessary. Avoid semicolons in prose, but do not modify code, commands, quoted errors, or configuration because they contain semicolons.

Do not implement universal bans on passive voice, the word 'is', or every '-ing' word. Grammatical role, meaning, permitted technical terminology, and the official rule's scope matter. Word substitution alone cannot preserve every technical meaning.

## Protect literal content

Keep commands, code, configuration keys and values, API identifiers, schema keys, paths, URLs, versions, requirement IDs, status codes, exact diagnostic messages, and quoted source text unchanged during a language-only edit. Explain these literals in surrounding prose. If repository verification proves that a command or literal is technically wrong, handle its correction as a separately justified documentation/contract change within task scope. Never silently rename an API field or alter an executable command for readability.

Preserve quantities, units, logical operators and boundaries, state names, counting conventions, exceptions, compatibility, release status, and historical rationale. In particular:

- 'should' must not become 'must' without an approved requirement change.
- 'might reduce memory use' must not become 'reduces memory use'.
- 'timeout exceeds 30 seconds' must not become 'fails after 30 seconds'.
- 'retry count is less than three' must not become 'retry up to three times'.
- 'start both actions together' must not become two sequential steps.
- 'planned' or 'proposed' must not become 'implemented', 'accepted', or 'released'.

## Apply by document role

- README: make supported setup and usage explicit. Keep project explanation natural and concise.
- PRD: preserve obligation, scope, uncertainty, and acceptance boundaries.
- ADR: retain alternatives, tradeoffs, assumptions, decision status, and historical rationale.
- Spec: make actors, conditions, state changes, and failure behavior clear without redesigning the system.
- OpenAPI: edit only authorized human-readable descriptions. Protect schema structure, keys, examples, and contract semantics. Respect authoritative generators.
- Test plan: state condition, action, and observable expected outcome. Do not imply an unexecuted test passed.
- Runbook: use the strongest procedural discipline. Identify prerequisites, environment, permissions, actions, results, and recovery limits.
- Changelog: retain versions, dates, compatibility, and actual release status.

## Three separate review passes

1. Mechanical review: inspect sentence length, punctuation, noun groups, and configured terminology in scoped English prose. Skip protected literals. Report approximate counting and unsupported checks. A mechanical pass is not dictionary, meaning, safety, or repository verification.
2. Language and meaning review: compare the original and revised text for actor, action, object, condition, sequence, simultaneity, obligation, uncertainty, quantities, units, boundaries, counting, and exceptions. For API prose also compare request/response identifiers, status codes, and compatibility. Flag unresolved meaning instead of guessing a cleaner interpretation.
3. Repository verification: check the documented commands, configuration, interfaces, requirements, generated ownership, operations, and release claims against available repository evidence. Execute only checks authorized by the task. Passing a language check does not authorize destructive operations or establish technical correctness.

Review the diff. Confirm that style changes did not alter technical meaning or protected literals. Do not turn a small bug fix into a repository-wide style rewrite. In Audit/read-only mode, report language findings and proposed wording without editing any file or TODO.md. Do not create speculative autogoal tasks for general style churn.

## Strict conformance and reporting

If strict ASD-STE100 conformance is requested, identify the official issue, review scope, governed technical terminology, applicable rules and dictionary, review method, and unresolved findings. If any required reference or competent review is unavailable, report the gap. Do not substitute sentence length, dictionary lookup, or AI plausibility for conformance review. ASD and STEMG do not endorse or certify software tools, including AI-based tools.

Normally report: 'Applied the project's STE-inspired writing profile. Reviewed scoped wording and meaning preservation. Full ASD-STE100 dictionary compliance was not verified.' State the actual mechanical, language, and repository checks performed and their separate limitations. Do not claim a review happened merely because the policy is installed.

Official references:
- https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf
- https://asd-ste100.org/STEsoftware.html
- https://asd-ste100.org/faq.html
- https://www.asd-ste100.org/assets/files/WhitePaper-ASD-STE100_and_AI.pdf
