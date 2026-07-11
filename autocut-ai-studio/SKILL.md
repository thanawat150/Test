---
name: autocut-ai-studio
description: Build and maintain an AI-assisted video editing application that removes silence, creates Thai subtitles, proposes hooks and story improvements, plans B-roll, adds controlled sound design, and exports reviewable platform-ready video drafts.
---

# AutoCut AI Studio

## Product goal

Build an AI Content Director that converts raw video into a reviewable edited draft.

The system should understand spoken content, remove unnecessary silence, create accurate subtitles, improve story structure, plan supporting visuals, and export platform-ready video without modifying the original source.

## Primary users

- Business and communication teams
- ESG, sustainability, forestry, carbon, survey, and field-operation teams
- Educators and subject-matter experts
- Creators without professional editing experience

## MVP scope

Implement and validate these capabilities first:

1. Import one video file.
2. Validate the media and confirm FFmpeg availability.
3. Detect silence from the audio track.
4. Preserve short natural pauses.
5. Remove only approved long silent sections.
6. Extract speech audio.
7. Transcribe Thai speech with timestamps.
8. Generate editable SRT subtitles.
9. Render a preview.
10. Export H.264 MP4.

Do not implement automatic AI video generation until this pipeline passes a real end-to-end test.

## Current technical stack

- UI: Streamlit for the MVP
- Processing: Python and FFmpeg
- AI: OpenAI API
- Local workspace: temporary project folders
- Future desktop shell: Tauri with React and TypeScript
- Future API layer: FastAPI
- Future database: SQLite

## Processing pipeline

Input video
→ validate media
→ inspect audio
→ detect silence
→ create edit decision list
→ preserve breathing gaps
→ render edited video
→ extract audio
→ transcribe speech
→ create subtitles
→ review
→ export

## Core rules

- Never expose or commit `OPENAI_API_KEY`.
- Never overwrite the original video.
- Store edits as reversible decisions whenever possible.
- Every automatic edit must have a reason.
- Preserve natural speech rhythm.
- Prefer deleting repeated ideas before deleting every pause.
- Do not fabricate facts, numbers, locations, or project evidence.
- Prefer user-provided media over generated media.
- Clearly distinguish generated media from real evidence.
- Do not claim that the application guarantees views.
- Review copyright and platform rules before using music, stock media, or sound effects.

## Editing principles

### Silence removal

- Keep short pauses between phrases.
- Add configurable padding before and after speech.
- Avoid cutting consonants, breaths that carry meaning, and sentence endings.
- Provide conservative, balanced, and aggressive presets.

### Subtitles

- Segment subtitles by meaning, not only character count.
- Keep Thai phrases together.
- Allow correction of names, technical terms, locations, units, and project codes.
- Keep subtitles inside platform safe zones.

### Story and retention

When added later, analyze:

- Topic strength
- Hook clarity
- Unanswered questions
- Repetition
- Story progression
- Evidence quality
- Payoff strength
- Platform fit

Call outputs `retention risks` or `editing recommendations`, not guaranteed predictions.

### B-roll

Use this priority:

1. Original footage
2. User project assets
3. Charts, maps, and graphics generated from real data
4. Licensed stock media
5. AI-generated images
6. AI-generated video

## Development order

1. Media validation
2. FFmpeg integration
3. Silence detection
4. Safe silence removal
5. Audio extraction
6. Thai transcription
7. Subtitle generation and correction
8. Preview and export
9. Hook generator
10. Story restructuring
11. Retention-risk map
12. B-roll planner
13. Sound design
14. Image generation
15. Video generation
16. Analytics learning loop

## Definition of done

A feature is complete only when:

- It works on a real Thai-language video.
- The source file remains unchanged.
- Errors are clearly shown to the user.
- Automatic decisions can be reviewed.
- Output can be previewed.
- Important processing logic has tests.
- A manual end-to-end test passes.
- README and relevant documentation are updated.
