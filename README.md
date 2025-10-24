# yt_autopilot

Automated end-to-end YouTube content creation and publishing system. From trend detection to video upload, fully automated with AI agents.

## What it does

1. **Find trending topics** using external trend sources
2. **Generate editorial plan** using multi-agent AI system (strategy, script, visuals)
3. **Produce video** using Google Veo API for video clips + TTS for voiceover
4. **Assemble final video** with ffmpeg (intro, outro, logo overlays)
5. **Upload to YouTube** with scheduled publish time
6. **Collect KPI metrics** from YouTube Analytics API
7. **Store everything** in local datastore for continuous improvement
8. **Run on scheduler** - fully autonomous, no manual triggers

**Zero dependency on n8n, Zapier, Make, or other external automation platforms.**

---

## Architecture

This project follows a strict **layered architecture** to maintain clean separation of concerns:

```
yt_autopilot/
├── core/           # Shared contracts, config, logging (NO external deps)
├── agents/         # AI editorial brain (NO side effects, NO I/O)
├── services/       # External operations (Veo, YouTube, ffmpeg, TTS)
├── pipeline/       # Orchestration (ONLY layer that uses agents + services)
└── io/             # Data persistence and exports
```

### Layer Rules (STRICT)

| Layer | Can Import From | Cannot Import From | Responsibilities |
|-------|----------------|-------------------|------------------|
| `core/` | Nothing outside core | All other layers | Data schemas, config, logger, memory |
| `agents/` | `core/` only | `services/`, `pipeline/` | AI reasoning, content generation (pure functions) |
| `services/` | `core/` only | `agents/`, `pipeline/` | External APIs, file I/O, video processing |
| `pipeline/` | `core/`, `agents/`, `services/` | `io/` (can use, not restricted) | Workflow orchestration |
| `io/` | `core/` | `agents/`, `services/` | Data storage and exports |

**Rule of thumb:**
- Agents = Brain (think, don't do)
- Services = Hands (do, don't think)
- Pipeline = Coordinator (tells brain to think, tells hands to do)

---

## Content Compliance & Brand Safety

All content generation **MUST** follow these rules:

### Prohibited Content
- Medical claims or guaranteed cures
- Hate speech or targeted harassment
- Aggressive political content
- Explicit copyrighted material references (e.g., "use [Famous Artist]'s song")
- Vulgar or offensive language

### Brand Tone
- **Positive and direct**
- **Helpful and informative**
- **Zero vulgarity**

### Visual Style
- **Format:** Vertical 9:16 (YouTube Shorts)
- **Pacing:** High rhythm, dynamic cuts
- **Overlays:** Large text overlays for key points
- **Colors:** Warm, engaging palette

Compliance checks are enforced in:
1. `core/memory_store.py` - maintains banned topics list
2. Agents layer - all generated content validated against rules
3. Publishing pipeline - final review before upload

---

## Setup

### 1. Clone and Install

```bash
git clone <your-repo-url>
cd yt_autopilot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. System Dependencies

Install `ffmpeg` (required for video assembly):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials
```

Required credentials:
- **LLM_API_KEY**: Your LLM provider API key (OpenAI, Anthropic, etc.)
- **VEO_API_KEY**: Google Veo API key for video generation
- **YOUTUBE_CLIENT_ID/SECRET/REFRESH_TOKEN**: YouTube OAuth credentials

To get YouTube OAuth tokens:
1. Create project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable YouTube Data API v3
3. Create OAuth 2.0 credentials
4. Use OAuth playground or run initial auth flow to get refresh token

### 4. Initialize Channel Memory

On first run, `channel_memory.json` will be created automatically with defaults. You can edit it to customize:

```json
{
  "brand_tone": "Your channel's tone",
  "visual_style": "Your visual identity",
  "banned_topics": ["topic1", "topic2"],
  "recent_titles": []
}
```

---

## Usage

(Implementation in progress - coming in future steps)

```bash
# Run full pipeline once
python -m yt_autopilot.pipeline.produce_render_publish

# Start automated scheduler
python -m yt_autopilot.pipeline.scheduler
```

---

## Data Flow

```
1. Trend Detection
   └─> TrendCandidate (core.schemas)

2. Editorial Brain (agents/)
   ├─> VideoPlan
   ├─> VideoScript
   ├─> VisualPlan
   ├─> PublishingPackage
   └─> ReadyForFactory (APPROVED/REJECTED)

3. Production (services/)
   ├─> Generate clips (Veo API → .mp4)
   ├─> Generate voiceover (TTS → .wav)
   ├─> Assemble video (ffmpeg)
   └─> Generate thumbnail

4. Publishing (services/)
   └─> Upload to YouTube → UploadResult

5. Analytics (services/)
   └─> Collect metrics → VideoMetrics

6. Storage (io/)
   └─> Save all data locally
```

---

## Development Principles

### Type Safety
- **All functions have type hints**
- **Pydantic models for all data structures** (defined in `core/schemas.py`)
- Run `mypy` for type checking

### Single Source of Truth
- **NEVER redefine data models** - always import from `core.schemas`
- **NEVER hardcode config** - always use `core.config.get_config()`

### Error Handling
- All errors logged via `core.logger`
- Graceful degradation where possible
- Clear error messages for debugging

### Testing
(To be implemented)
- Unit tests for agents (pure functions, easy to test)
- Integration tests for services
- End-to-end tests for pipeline

---

## Roadmap

- [x] Step 01: Core foundation (schemas, config, logger, memory)
- [ ] Step 02: Implement agents (TrendHunter, ScriptWriter, VisualPlanner, etc.)
- [ ] Step 03: Implement services (Veo, TTS, ffmpeg, YouTube)
- [ ] Step 04: Build pipeline orchestrators
- [ ] Step 05: Implement scheduler for automation
- [ ] Step 06: Analytics feedback loop
- [ ] Step 07: Quality improvements and testing

---

## Contributing

When adding new features:

1. **Check layer boundaries** - respect import restrictions
2. **Add types to schemas first** - if you need new data structures, add them to `core/schemas.py`
3. **Log everything** - use `from yt_autopilot.core.logger import logger`
4. **Update this README** - document new components

---

## License

(Add your license here)

---

## Support

For issues, questions, or contributions, please open an issue on GitHub.
