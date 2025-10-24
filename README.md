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

## Agents Layer: The Editorial Brain

The `agents/` layer contains five specialized AI agents that work together to generate video concepts and scripts. All agents are **pure functions** - they take structured inputs and return structured outputs with **zero side effects**.

### Agent Roles

#### 1. TrendHunter (`trend_hunter.py`)
**Function:** `generate_video_plan(trends: List[TrendCandidate], memory: Dict) -> VideoPlan`

**Responsibilities:**
- Analyzes trending topics from multiple sources
- Filters out banned topics and content too similar to recent videos
- Ranks trends by momentum score and strategic fit
- Selects the most promising topic for the day
- Generates strategic video plan with compliance notes

**Key Features:**
- Avoids repetition by checking recent titles
- Respects brand safety rules
- Infers target audience based on topic characteristics

#### 2. ScriptWriter (`script_writer.py`)
**Function:** `write_script(plan: VideoPlan, memory: Dict) -> VideoScript`

**Responsibilities:**
- Creates engaging hook for first 3 seconds
- Generates content bullets covering key points
- Writes compelling call-to-action
- Composes complete voiceover text

**Key Features:**
- Respects channel's brand tone
- Optimizes for viewer retention
- Structures content for YouTube Shorts format

#### 3. VisualPlanner (`visual_planner.py`)
**Function:** `generate_visual_plan(plan: VideoPlan, script: VideoScript, memory: Dict) -> VisualPlan`

**Responsibilities:**
- Divides script into visual scenes
- Generates Veo API prompts for each scene
- Estimates duration per scene
- Ensures consistent visual style

**Key Features:**
- Optimized for 9:16 vertical format
- Applies channel's visual style consistently
- Warns if total duration exceeds Shorts limits (~60s)

#### 4. SeoManager (`seo_manager.py`)
**Function:** `generate_publishing_package(plan: VideoPlan, script: VideoScript) -> PublishingPackage`

**Responsibilities:**
- Optimizes title for CTR (max 100 chars)
- Generates SEO-rich description with keywords
- Extracts relevant tags (max 500 chars total)
- Creates thumbnail concept for visual appeal
- Adds placeholder affiliate links

**Key Features:**
- Balances curiosity and clarity in titles
- Avoids clickbait spam patterns
- Includes timestamps and CTAs in description

#### 5. QualityReviewer (`quality_reviewer.py`)
**Function:** `review(plan, script, visuals, publishing, memory) -> Tuple[bool, str]`

**Responsibilities:**
- **Final gatekeeper before production**
- Checks for banned topics and hate speech
- Verifies no prohibited medical/legal claims
- Ensures copyright compliance
- Validates brand tone consistency
- Checks hook quality and title standards
- Verifies video duration is appropriate

**Returns:**
- `(True, "OK")` if all checks pass → APPROVED
- `(False, "reason")` if issues found → REJECTED

**Key Features:**
- Comprehensive compliance verification
- Multi-point quality checks
- Detailed rejection reasons for improvement

### Agent Workflow

```
TrendCandidate[] → TrendHunter → VideoPlan
                                     ↓
                    ScriptWriter ← VideoPlan + Memory
                         ↓
                   VideoScript
                         ↓
              VisualPlanner ← VideoScript + VideoPlan + Memory
                         ↓
                   VisualPlan
                         ↓
             SeoManager ← VideoScript + VideoPlan
                         ↓
              PublishingPackage
                         ↓
        QualityReviewer ← ALL components + Memory
                         ↓
                 APPROVED / REJECTED
```

**Important:** Agents never touch the filesystem, call external APIs, or perform I/O operations. They only reason and generate structured data using models from `core/schemas.py`.

---

## Pipeline Layer: Orchestration

The `pipeline/` layer coordinates agents (and eventually services) to execute complete workflows. This is the **only layer allowed to import from both agents and services**.

### build_video_package.py - Editorial Brain Orchestrator

**Function:** `build_video_package() -> ReadyForFactory`

**Purpose:**
The main orchestrator for the editorial pipeline. Coordinates all AI agents in sequence to produce a complete, quality-approved content package ready for production.

**What it does:**
1. **Loads channel memory** - retrieves brand tone, banned topics, recent titles
2. **Gets trending topics** - currently uses mock data, will integrate with trend services later
3. **Runs TrendHunter** - selects best topic avoiding banned content and duplicates
4. **Runs ScriptWriter** - generates engaging script with hook, bullets, and CTA
5. **Runs VisualPlanner** - creates scene-by-scene visual plan for video generation
6. **Runs SeoManager** - optimizes title, description, tags, and thumbnail concept
7. **Runs QualityReviewer** - performs 8-point compliance and quality check
8. **Handles rejection** - if rejected, attempts ONE revision:
   - Improves script based on feedback
   - Regenerates visual plan and publishing metadata
   - Re-runs quality review
9. **Updates memory** - if approved, adds title to `recent_titles` to avoid repetition
10. **Returns package** - `ReadyForFactory` with status "APPROVED" or "REJECTED"

**What is ReadyForFactory?**

`ReadyForFactory` is the complete editorial package that contains:
- **status**: "APPROVED" or "REJECTED"
- **video_plan**: Strategic video concept
- **script**: Complete voiceover script
- **visuals**: Scene-by-scene visual plan
- **publishing**: SEO-optimized metadata (title, description, tags, thumbnail)
- **rejection_reason**: Explanation if rejected (None if approved)

**Memory Management:**

When a package is **APPROVED**:
- The final title is added to `channel_memory.json` → `recent_titles[]`
- This prevents future videos from being too similar
- Memory is persisted via `save_memory()`

When a package is **REJECTED**:
- Memory is **NOT** updated
- The rejected content does not pollute the title history
- Logs contain detailed rejection reasons for debugging

**Key Features:**
- ✅ Fully automated editorial decision-making
- ✅ Built-in quality control with retry mechanism
- ✅ Compliance enforcement before production
- ✅ Memory management for content diversity
- ❌ Does NOT call external APIs (Veo, YouTube, etc.)
- ❌ Does NOT generate video files
- ❌ Does NOT upload content

**This is the final step of the "editorial brain" before physical video production.**

**Example Usage:**
```python
from yt_autopilot.pipeline import build_video_package

# Generate complete editorial package
package = build_video_package()

if package.status == "APPROVED":
    print(f"✓ Approved: {package.publishing.final_title}")
    print(f"  Duration: ~{sum(s.est_duration_seconds for s in package.visuals.scenes)}s")
    print(f"  Scenes: {len(package.visuals.scenes)}")
    # Ready for video production (Step 04)
else:
    print(f"✗ Rejected: {package.rejection_reason}")
    # Can analyze and improve based on feedback
```

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
- [x] Step 02: Implement agents (TrendHunter, ScriptWriter, VisualPlanner, SeoManager, QualityReviewer)
- [x] Step 03: Editorial pipeline orchestrator (build_video_package)
- [ ] Step 04: Implement services (Veo, TTS, ffmpeg, YouTube, analytics, datastore)
- [ ] Step 05: Full production pipeline (produce_render_publish)
- [ ] Step 06: Implement scheduler for automation
- [ ] Step 07: Analytics feedback loop and continuous improvement
- [ ] Step 08: Quality improvements and testing

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
