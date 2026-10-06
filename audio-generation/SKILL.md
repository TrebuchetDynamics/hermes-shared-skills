---
name: audio-generation
description: Use when creating spoken audio. Match voice to language.
version: 1.0.0
license: MIT
author: Hermes fleet agent
metadata:
  hermes:
    tags: [audio, speech, tts, creative]
---

# Audio Generation

Generate spoken audio that matches the user's requested language, voice, tone, and delivery format. Keep the script faithful to the source and make the rendered speech—not just the text—the acceptance target.

## When to Use

Use when creating narration, voiceovers, spoken summaries, or other text-to-speech audio. This skill covers language/voice selection, script preparation, generation, and rendered-audio verification.

## Workflow

1. **Confirm the brief from context.** Identify the requested language, audience, tone, length, and output format. Preserve the user's language requirement even when the surrounding conversation is in another language.
2. **Select a language-matched voice explicitly.** Choose a voice whose locale and pronunciation fit the requested language and audience. Do not assume that writing the script in a language, or asking for that language in generic style instructions, will cause the provider to render it with a matching voice. If the provider supports explicit voice selection, set it directly.
3. **Prepare the script.** Use natural spoken phrasing, expand ambiguous abbreviations when needed, and retain factual qualifications. For business summaries, distinguish current implementation from deployment, acceptance, and plans.
4. **Generate the requested artifact.** Use the available TTS tool/provider and save the output at a user-accessible path when an artifact is requested. Do not claim generation or delivery until the tool confirms it.
5. **Verify the rendered speech.** Listen to the output when playback is available, checking language, pronunciation, pacing, completeness, and clipping. If the output is unavailable for playback, state that voice quality was not verified; do not imply that the selected voice guarantees correct rendering.
6. **Correct and redeliver when needed.** If the rendered language or voice does not match the brief, regenerate with an explicitly appropriate voice/provider and verify the replacement. Do not defend a mismatched artifact based only on the script language.

## Guardrails

- Do not invent facts to improve the narration; preserve uncertainty and source limitations.
- Do not include secrets, private user data, or credentials in scripts.
- Keep the final handoff concise and include the artifact location or attachment. State any material verification limitation.