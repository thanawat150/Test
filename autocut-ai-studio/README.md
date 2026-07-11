# AutoCut AI Studio

AI-assisted video editing MVP for Thai-language creators and business teams.

## Current MVP

- Upload a video
- Detect silent sections with FFmpeg
- Remove long silence while preserving natural pauses
- Extract audio
- Generate Thai subtitles with OpenAI Speech-to-Text
- Download edited MP4 and SRT
- Keep all source files unchanged

## Planned roadmap

1. Hook generator
2. Story restructuring
3. Retention-risk map
4. B-roll planner
5. Sound-effect placement
6. AI image and video generation
7. Multi-platform exports
8. Analytics learning loop

## Requirements

- Python 3.11+
- FFmpeg available in PATH
- OpenAI API key

## Run locally

```bash
cd autocut-ai-studio
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

Open the local URL shown by Streamlit.

## Environment

Create `.env`:

```env
OPENAI_API_KEY=your_key_here
```

Never commit the real API key.

## Important limitations

- The MVP removes silence and creates subtitles; it does not yet guarantee viral performance.
- Review every automated cut before publishing.
- AI-generated media must be labeled separately from real project evidence.
- Use only music, sound effects, and stock assets that you are licensed to use.
