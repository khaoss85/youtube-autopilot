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

### produce_render_publish.py - Full Production Pipeline with Human Gate

**Functions:** `produce_render_assets()`, `publish_after_approval()`

**Purpose:**
Complete production pipeline that transforms editorial packages into published YouTube videos. Includes a **mandatory human approval step** to ensure brand safety.

⚠️ **CRITICAL BRAND SAFETY FEATURE:**
This pipeline has a **human-in-the-loop gate** before publication. The system generates content but **NEVER uploads to YouTube automatically**. Human review and explicit approval are required.

**Two-Phase Workflow:**

#### Phase 1: `produce_render_assets(publish_datetime_iso: str)` → HUMAN_REVIEW_PENDING

Generates all physical assets and saves them for human review.

**Steps:**
1. Run editorial brain (`build_video_package()`)
2. If REJECTED by quality reviewer → abort
3. If APPROVED → generate physical assets:
   - Generate video scenes (Veo API)
   - Generate voiceover (TTS)
   - Assemble final video (ffmpeg)
   - Generate thumbnail image
4. Save to datastore with state **"HUMAN_REVIEW_PENDING"**
5. Return draft package info

**Output:**
```python
{
    "status": "READY_FOR_REVIEW",
    "video_internal_id": "123e4567-...",  # UUID for this draft
    "final_video_path": "./output/final_video.mp4",
    "thumbnail_path": "./output/thumbnail.png",
    "proposed_title": "Video Title",
    "proposed_description": "SEO description...",
    "proposed_tags": ["tag1", "tag2"],
    "suggested_publishAt": "2025-10-25T18:00:00Z"
}
```

**At this point:**
- ✅ Video is fully produced and ready to watch
- ✅ All assets saved locally
- ❌ **NOT uploaded to YouTube**
- ⏸️ Waiting for human review

#### Phase 2: `publish_after_approval(video_internal_id: str)` → SCHEDULED_ON_YOUTUBE

Uploads approved video to YouTube (MANUAL TRIGGER ONLY).

**Steps:**
1. Retrieve draft package from datastore
2. Validate state is "HUMAN_REVIEW_PENDING"
3. Upload video to YouTube with scheduled publication
4. Set custom thumbnail
5. Update datastore state to **"SCHEDULED_ON_YOUTUBE"**

**Output:**
```python
{
    "status": "SCHEDULED",
    "video_id": "abc123xyz",  # YouTube video ID
    "publishAt": "2025-10-25T18:00:00Z",
    "title": "Video Title"
}
```

**Security:**
- ⚠️ This function MUST NEVER be called automatically by a scheduler
- ⚠️ Only called after explicit human approval
- ⚠️ Single point of YouTube upload in entire system

**Example Usage:**
```python
from yt_autopilot.pipeline import produce_render_assets, publish_after_approval

# Phase 1: Generate assets
result = produce_render_assets("2025-10-25T18:00:00Z")

if result["status"] == "READY_FOR_REVIEW":
    # Human reviews video at: result["final_video_path"]
    # Human checks thumbnail, title, description, tags
    # Human decides: approve or reject

    # If approved:
    upload = publish_after_approval(result["video_internal_id"])
    print(f"Scheduled: {upload['video_id']}")
else:
    print(f"Rejected: {result['reason']}")
```

### tasks.py - Reusable Tasks for Scheduler

**Functions:** `task_generate_assets_for_review()`, `task_publish_after_human_ok()`, `task_collect_metrics()`

**Purpose:**
Atomic task wrappers for the automation scheduler (Step 06). These tasks can be scheduled to run at specific times.

#### Task 1: `task_generate_assets_for_review(publish_datetime_iso: str)`

**Can be automated:** ✅ YES (does NOT publish publicly)

Generates video assets and saves as draft for human review. This task is safe to automate because it only creates drafts in "HUMAN_REVIEW_PENDING" state.

**Scheduler usage:**
```python
# Runs daily at 10:00 AM
result = task_generate_assets_for_review("2025-10-25T18:00:00Z")
# → Sends notification to human reviewer
```

#### Task 2: `task_publish_after_human_ok(video_internal_id: str)`

**Can be automated:** ❌ NO (requires manual trigger)

Uploads approved video to YouTube. This task MUST NEVER be scheduled automatically. It must only be called manually after human approval.

**Manual usage:**
```python
# Human approves, then manually triggers:
result = task_publish_after_human_ok("123e4567-...")
```

#### Task 3: `task_collect_metrics()`

**Can be automated:** ✅ YES (read-only operation)

Collects analytics metrics for all scheduled videos. Safe to automate because it only reads data from YouTube Analytics.

**Scheduler usage:**
```python
# Runs daily at midnight
task_collect_metrics()
# → Updates datastore with latest views, CTR, watch time
```

### Video Lifecycle: From Idea to Published

Complete workflow showing how a video goes from trending topic to published content:

**Step 1: Editorial Brain**
```
build_video_package() → ReadyForFactory (status: APPROVED)
```
- AI agents generate content package
- Quality reviewer performs 8-point compliance check
- Memory updated with new title to avoid duplicates

**Step 2: Asset Generation**
```
produce_render_assets() → Draft Package (state: HUMAN_REVIEW_PENDING)
```
- Veo generates video scenes
- TTS generates voiceover
- ffmpeg assembles final video
- Image gen creates thumbnail
- Saved to datastore with UUID

**Step 3: Human Review** ⚠️ **CRITICAL GATE**
```
Human reviews:
- Watches final video
- Checks thumbnail quality
- Reviews title, description, tags
- Verifies brand compliance
- Decides: APPROVE or REJECT
```

**Step 4: Publication** (only if approved)
```
publish_after_approval() → YouTube Upload (state: SCHEDULED_ON_YOUTUBE)
```
- Uploads video to YouTube
- Sets custom thumbnail
- Schedules publication time
- Returns YouTube video ID

**Step 5: Analytics Collection**
```
task_collect_metrics() → VideoMetrics saved to datastore
```
- Fetches views, watch time, CTR from YouTube Analytics
- Saves time-series metrics for historical tracking
- Runs daily to keep KPIs updated

**Step 6: Reporting**
```
export_report_csv() → CSV file for analysis
```
- Exports performance report with latest metrics
- Used for strategy optimization and ROI analysis

**Data Flow:**
```
TrendCandidate → VideoPlan → VideoScript → VisualPlan → PublishingPackage
                                                              ↓
                                                        (APPROVED)
                                                              ↓
Scene clips + Voiceover + Thumbnail → Final Video → HUMAN_REVIEW_PENDING
                                                              ↓
                                                        (HUMAN OK)
                                                              ↓
                                        YouTube Upload → SCHEDULED_ON_YOUTUBE
                                                              ↓
                                        Analytics → VideoMetrics → CSV Report
```

**Why Human-in-the-Loop?**

1. **Brand Safety:** Prevents publishing inappropriate or off-brand content
2. **Legal Compliance:** Human verifies no copyright, medical claims, hate speech
3. **Quality Control:** Final check for production quality and messaging
4. **Reputation Management:** Zero risk of automated reputational damage
5. **Regulatory Compliance:** Meets content platform policies

The system is **semi-autonomous**: it automates content creation but requires human judgment for publication.

---

## Human Review & Approval Flow (run.py review)

The system uses a **2-gate workflow** to minimize wasted costs and ensure quality:

### Gate 1: Script Review (Cheap - ~$0.01)

**Before generating expensive assets ($5-10), review and approve the script:**

```bash
# List scripts pending review (filtered by active workspace)
python run.py review scripts

# Show script details (concept + scene breakdown)
python run.py review show-script <script_id>

# Approve script to trigger asset generation
python run.py review approve-script <script_id> --approved-by "you@company"
```

**Why Gate 1:**
- Reject bad concepts BEFORE spending money on Sora/TTS
- Edit script if needed before asset generation
- Quick review (no video to watch yet)

### Gate 2: Video Review (After Assets Generated)

**After assets are generated, review the final video:**

```bash
# List videos pending review (filtered by active workspace)
python run.py review list

# Show video details + quality check
python run.py review show <video_id>

# Approve and publish to YouTube
python run.py review publish <video_id> --approved-by "you@company"
```

### Workflow Steps

**Step 1: Generate and review script (Gate 1)**
```bash
# Generate video using active workspace
python run.py generate

# Review generated scripts
python run.py review scripts

# Check script details
python run.py review show-script abc-123

# Approve if good
python run.py review approve-script abc-123 --approved-by "dan@company"
```

**Step 2: Generate assets (automated or manual)**
```python
# After script approval, trigger asset generation
from yt_autopilot.pipeline.produce_render_publish import produce_render_assets
produce_render_assets(script_internal_id="abc-123")
```

**Step 3: Review and publish video (Gate 2)**
```bash
# List videos ready for review
python run.py review list

# Watch the video and check quality
python run.py review show 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d

# Approve and upload to YouTube
python run.py review publish 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d --approved-by "dan@company"
```

### Workspace Filtering

Review commands automatically filter by active workspace:

```bash
# Shows only scripts/videos from current workspace
python run.py review scripts
python run.py review list

# Show scripts/videos from ALL workspaces
python run.py review scripts --all-workspaces
python run.py review list --all-workspaces
```

### Audit Trail

Every approval is tracked with:
- `approved_by`: Identifier of approver (e.g., "dan@company")
- `approved_at_iso`: UTC timestamp of approval
- `youtube_video_id`: Final YouTube video ID (after publishing)
- `script_internal_id`: Link to approved script (Gate 1 → Gate 2)

### Important Constraints

⚠️ **The `publish` command is the ONLY way to upload videos to YouTube.**

⚠️ **This command must NEVER be automated or scheduled.**

The review workflow is the final brand safety gate. Humans must explicitly approve scripts and videos before publication.

---

## Services & IO Layer: The Factory

The `services/` and `io/` layers handle all **external operations and data persistence**. These are the "physical hands" of the system - they transform editorial packages (`ReadyForFactory`) into real videos and manage historical data.

**Key Principle:** Services and IO modules can ONLY import from `core/`. They NEVER import from `agents/` or `pipeline/`. This strict separation ensures agents remain pure reasoning functions.

### Services: External Operations

All services are currently **stubs with TODO comments** for future API integration. The only exception is `video_assemble_service.py`, which has a real ffmpeg implementation.

#### 1. Trend Source (`trend_source.py`)
**Function:** `fetch_trends() -> List[TrendCandidate]`

**Purpose:** Fetch trending topics from external sources

**TODO Integration:**
- Google Trends API
- Twitter/X trending topics
- Reddit popular posts
- YouTube trending videos

**Current Status:** Returns 5 mock `TrendCandidate` objects

#### 2. Video Generation Service (`video_gen_service.py`)
**Function:** `generate_scenes(visual_plan: VisualPlan, max_retries: int = 2) -> List[str]`

**Purpose:** Generate video clips using Google Veo API

**TODO Integration:**
- Google Veo 3.x API
- Vertical 9:16 format, 1080p resolution
- 10-30 second clips
- Retry logic with exponential backoff (2^attempt seconds)
- ~2-5 minutes generation time per clip

**Current Status:** Returns mock .mp4 file paths with placeholder files

#### 3. Text-to-Speech Service (`tts_service.py`)
**Function:** `synthesize_voiceover(script: VideoScript, voice_id: str) -> str`

**Purpose:** Convert script text to speech audio

**TODO Integration (recommended: ElevenLabs):**
- **ElevenLabs:** Best quality, ~$0.30/1K chars, natural intonation
- Google Cloud TTS: Budget option, ~$4/1M chars
- Amazon Polly: AWS ecosystem integration
- Azure TTS: Microsoft ecosystem integration

**Current Status:** Returns mock .wav file path

#### 4. Thumbnail Service (`thumbnail_service.py`)
**Function:** `generate_thumbnail(publishing: PublishingPackage) -> str`

**Purpose:** Generate eye-catching thumbnail images

**TODO Integration:**
- DALL-E 3, Midjourney, or Stable Diffusion
- Specifications: 1080x1920 (9:16 vertical), PNG/JPG, max 2MB
- High contrast text overlays for readability

**Current Status:** Returns mock .png file path

#### 5. Video Assembly Service (`video_assemble_service.py`) ✅ REAL IMPLEMENTATION
**Function:** `assemble_final_video(scene_paths: List[str], voiceover_path: str, visuals: VisualPlan) -> str`

**Purpose:** Assemble final video from scenes and audio using ffmpeg

**Implementation:**
- Real ffmpeg subprocess integration
- Creates concat file for scene clips
- Concatenates clips with `ffmpeg -f concat`
- Mixes voiceover audio with `-c:a aac`
- Video encoding: `-c:v libx264 -preset fast -crf 23`
- Audio encoding: `-b:a 128k`

**Requirements:** ffmpeg must be installed on system

**Current Status:** ✅ Fully functional

#### 6. YouTube Uploader (`youtube_uploader.py`)
**Function:** `upload_and_schedule(video_path, publishing, publish_datetime_iso, thumbnail_path) -> UploadResult`

**Purpose:** Upload videos to YouTube with scheduled publication

**TODO Integration:**
- YouTube Data API v3
- OAuth 2.0 authentication with refresh token
- `videos.insert()` for upload with progress monitoring
- `thumbnails.set()` for custom thumbnail
- `publishAt` field for scheduled publishing
- Privacy status: "private" until scheduled time

**Current Status:** Returns mock `UploadResult` with generated video ID

#### 7. YouTube Analytics (`youtube_analytics.py`)
**Function:** `fetch_video_metrics(video_id: str) -> VideoMetrics`

**Purpose:** Collect performance metrics from YouTube

**TODO Integration:**
- YouTube Analytics API v2 (different from Data API!)
- Metrics: views, estimatedMinutesWatched, averageViewDuration, ctr
- Requires separate OAuth scope: youtube.readonly

**Current Status:** Returns mock `VideoMetrics` with realistic ranges (100-5000 views, 2-8% CTR)

### I/O: Data Persistence and Exports

The `io/` layer manages all local data storage using **JSONL files** for simplicity and append-only write patterns.

#### Datastore (`datastore.py`)

**Purpose:** Local database for video packages and metrics

**Storage Format:** JSONL (JSON Lines) - one JSON object per line

**Files:**
- `data/records.jsonl`: Complete video packages
- `data/metrics.jsonl`: Time-series analytics data

**Functions:**

**`save_video_package(ready, scene_paths, voiceover_path, final_video_path, upload_result)`**
- Saves complete editorial package + file paths + upload result
- Appends to `records.jsonl`
- Stores: video_plan, script, visuals, publishing, files, upload_result

**`list_published_videos() -> List[Dict]`**
- Returns basic metadata for all videos
- Fields: youtube_video_id, title, publish_at, saved_at, status

**`save_metrics(video_id, metrics)`**
- Appends metrics snapshot to `metrics.jsonl`
- For time-series tracking of video performance

**`get_metrics_history(video_id) -> List[VideoMetrics]`**
- Retrieves all metric snapshots for a video
- Ordered by collection time

#### Exports (`exports.py`)

**Purpose:** Export data to CSV for external analysis

**Functions:**

**`export_report_csv(csv_path: Optional[str] = None) -> str`**
- Exports performance report to CSV
- Columns: youtube_video_id, title, publish_at, status, views_latest, ctr_latest, avg_view_duration_latest, watch_time_latest
- Joins video records with latest metrics
- Default path: `./data/report.csv`

**`export_metrics_timeseries_csv(video_id: str, csv_path: Optional[str] = None) -> str`**
- Exports time-series metrics for single video
- Columns: collected_at, views, watch_time_seconds, average_view_duration_seconds, ctr
- Default path: `./data/metrics_{video_id}.csv`

### Why JSONL instead of SQLite?

- **Simplicity:** No database schema migrations
- **Append-only:** Fast writes, no locking
- **Debuggable:** Easy to grep/tail for inspection
- **Portable:** Works on any system without dependencies

### Service Layer Architecture Principles

1. **No Cross-Layer Pollution:**
   - Services NEVER import from `agents/`
   - Services NEVER import from `pipeline/`
   - Only `pipeline/` can coordinate agents + services

2. **Retry Logic:**
   - All external API calls should implement exponential backoff
   - Template in `video_gen_service.py`: 2^attempt seconds delay

3. **Logging:**
   - All operations logged with clear progress indicators
   - Warnings for mock/stub implementations

4. **Error Handling:**
   - Graceful degradation where possible
   - Clear error messages with context

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

## Quick Start for Claude Code Users

If you're using **Claude Code**, here's the fastest way to get started:

### 1. Initial Setup (One-Time)

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Install ffmpeg
brew install ffmpeg  # macOS
```

### 2. Create Your First Workspace

```bash
# Interactive workspace creation
python run.py workspace create
# Follow prompts: workspace_id, name, vertical, brand_tone

# Or switch to existing workspace
python run.py workspace list
python run.py workspace switch tech_ai_creator
```

### 3. Generate First Video

```bash
# Generate content for active workspace
python run.py generate

# Review the script (Gate 1 - cheap)
python run.py review scripts
python run.py review show-script <script_id>

# Approve script (triggers asset generation)
python run.py review approve-script <script_id> --approved-by "you@company"
```

### 4. Essential Commands Reference

```bash
# Workspace commands
python run.py workspace list      # List all workspaces
python run.py workspace info      # Show active workspace
python run.py workspace switch <id>  # Switch workspace

# Generation
python run.py generate            # Generate content

# Review (workspace-filtered by default)
python run.py review scripts      # List scripts
python run.py review list         # List videos
python run.py review show <id>    # Show details

# Cross-workspace view
python run.py review scripts --all-workspaces
python run.py review list --all-workspaces
```

### Claude Code Development Tips

**File Navigation:**
- Main CLI: `run.py`
- Pipeline: `yt_autopilot/pipeline/build_video_package.py`
- Agents: `yt_autopilot/agents/`
- Services: `yt_autopilot/services/`
- Datastore: `yt_autopilot/io/datastore.py`

**Testing:**
```bash
# Test workspace system
python run.py workspace list

# Test generation (uses mock trends if API keys not configured)
python run.py generate

# Check datastore
python run.py review stats
```

**Common Tasks:**
```bash
# Switch between channels
python run.py workspace switch tech_ai_creator
python run.py workspace switch gym_fitness_pro

# Review pending items
python run.py review scripts
python run.py review list

# Get help
python run.py --help
python run.py workspace --help
python run.py review --help
```

---

## Usage

### Quick Start

```bash
# 1. List available workspaces
python run.py workspace list

# 2. Switch to a workspace (or create one)
python run.py workspace switch tech_ai_creator

# 3. Generate video content
python run.py generate

# 4. Review and approve script (Gate 1)
python run.py review scripts
python run.py review show-script <script_id>
python run.py review approve-script <script_id> --approved-by "you@company"

# 5. (After assets generated) Review and publish video (Gate 2)
python run.py review list
python run.py review show <video_id>
python run.py review publish <video_id> --approved-by "you@company"
```

### CLI Command Reference

**Workspace Management:**
```bash
python run.py workspace list              # List all workspaces
python run.py workspace info              # Show active workspace details
python run.py workspace switch <id>       # Switch to workspace
python run.py workspace create            # Create new workspace (interactive)
```

**Content Generation:**
```bash
python run.py generate                    # Generate video using active workspace
python run.py generate --use-llm-curation # Use LLM for trend curation (Phase B)
```

**Script Review (Gate 1):**
```bash
python run.py review scripts                              # List scripts (active workspace)
python run.py review scripts --all-workspaces             # List scripts (all workspaces)
python run.py review show-script <script_id>              # Show script details
python run.py review approve-script <script_id> --approved-by "you@company"
```

**Video Review (Gate 2):**
```bash
python run.py review stats                                # Show datastore statistics
python run.py review list                                 # List videos (active workspace)
python run.py review list --all-workspaces                # List videos (all workspaces)
python run.py review show <video_id>                      # Show video details
python run.py review publish <video_id> --approved-by "you@company"
```

### Multi-Channel Workflow Example

```bash
# Morning: Tech channel
python run.py workspace switch tech_ai_creator
python run.py generate
python run.py review scripts

# Afternoon: Fitness channel
python run.py workspace switch gym_fitness_pro
python run.py generate
python run.py review scripts

# Evening: Review all pending videos
python run.py review list --all-workspaces
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

## 🔌 Provider Integration (Step 06-pre)

**Status:** Ready for live use with real API keys

Step 06-pre introduces **multi-provider LLM support** and **Veo/Vertex AI video generation** with graceful fallback when keys are missing.

### LLM Router (`services/llm_router.py`)

Centralized LLM access with automatic provider selection:

```python
from yt_autopilot.services.llm_router import generate_text

result = generate_text(
    role="script_writer",
    task="Generate viral hook for YouTube Shorts",
    context="Topic: AI automation tools",
    style_hints={"brand_tone": "casual", "target_audience": "creators"}
)
```

**Provider Priority:**
1. **Anthropic Claude** (if `LLM_ANTHROPIC_API_KEY` set) - Uses `claude-3-5-sonnet-20241022`
2. **OpenAI GPT** (if `LLM_OPENAI_API_KEY` set) - Uses `gpt-4o`
3. **Fallback** - Returns `[LLM_FALLBACK]` placeholder if no keys available

**Features:**
- Automatic provider failover
- Graceful degradation (system works without LLM)
- Consistent interface across providers
- Error handling and logging

### Video Generation (`services/video_gen_service.py`)

Enhanced with Veo/Vertex AI integration structure:

```python
from yt_autopilot.services.video_gen_service import generate_scenes

# Public API unchanged - maintains backward compatibility
scene_paths = generate_scenes(visual_plan, max_retries=2)
```

**Integration Status:**
- ✓ Reads `VEO_API_KEY` from config
- ✓ Prepares realistic Vertex AI API calls
- ✓ Endpoint structure ready: `https://us-central1-aiplatform.googleapis.com/v1/...`
- ✓ Payload includes prompt, duration, aspect ratio (9:16 for Shorts)
- ✓ Graceful fallback to placeholder files if key missing
- TODO: Complete job polling and binary download logic

**Current Behavior:**
- With VEO_API_KEY: Logs API readiness, uses placeholder (job polling TODO)
- Without VEO_API_KEY: Generates placeholder `.mp4` files for testing

### Configuration

Add keys to `.env`:

```bash
# Copy from .env.example
cp .env.example .env

# Edit .env with your keys
LLM_ANTHROPIC_API_KEY=sk-ant-api03-...  # Anthropic Claude
LLM_OPENAI_API_KEY=sk-proj-...          # OpenAI GPT
VEO_API_KEY=...                         # Google Vertex AI / Veo
```

**Config Getters:**
```python
from yt_autopilot.core.config import (
    get_llm_anthropic_key,
    get_llm_openai_key,
    get_veo_api_key
)
```

### Agent Integration Strategy

Agents remain **pure functions** and do NOT import from `services/`. LLM integration happens in the **pipeline layer**:

```python
# Future enhancement in pipeline/build_video_package.py

from yt_autopilot.services.llm_router import generate_text
from yt_autopilot.agents import write_script

# Pipeline calls LLM
llm_script = generate_text(
    role="script_writer",
    task="Write viral YouTube Shorts script",
    context=f"Topic: {plan.topic}",
    style_hints={"brand_tone": memory["brand_tone"]}
)

# Pipeline passes LLM output to agent
script = write_script(plan, memory, llm_suggestions=llm_script)
```

This maintains architectural layering: agents stay testable and deterministic.

### Testing Provider Integration

Run the integration test:

```bash
python test_step06_pre_live_generation.py
```

**Test Verifies:**
- ✓ Config module with new LLM provider getters
- ✓ LLM Router import and basic call (fallback if no keys)
- ✓ Video Generation Service import and mock call
- ✓ No breaking changes to existing code

**With API Keys:**
Test makes real LLM calls and prepares for real Veo calls.

**Without API Keys:**
Test uses fallback mode - system continues to work with mock intelligence.

### Architecture Notes

**Why llm_router is a service:**
- Services handle external API calls
- Agents remain pure reasoning functions
- Pipeline layer orchestrates LLM → Agent flow

**Why agents don't import llm_router:**
- Maintains strict layering (agents → core only)
- Keeps agents testable without API dependencies
- Pipeline injects LLM-generated context into agents

**Fallback Strategy:**
- Missing keys don't crash the system
- Deterministic fallback allows testing without APIs
- Production deployment requires real keys for quality

### Next Steps

1. **For Local Testing:**
   - Add at least one LLM key to `.env`
   - Run `test_step06_pre_live_generation.py`
   - Verify LLM calls work

2. **For Video Generation:**
   - Add `VEO_API_KEY` to `.env`
   - Complete TODO: job polling logic in `video_gen_service.py`
   - Test real video generation

3. **For Production:**
   - Configure all provider keys
   - Integrate LLM calls into pipeline (build_video_package.py)
   - Complete Veo job polling and download
   - Remove fallback warnings from logs

---

---

## Development History

Questo progetto è stato sviluppato in step incrementali (Step 01 → Step 08).

Per documentazione dettagliata di ogni step, consulta: **[docs/history.md](docs/history.md)**

**Highlights:**
- ✅ Step 01-05: Core foundation + agents + services + pipeline
- ✅ Step 06: First playable build
- ✅ Step 07.x: Real generation + quality improvements + 2-gate workflow
- ✅ Step 08: Multi-workspace system + unified CLI

---

## Roadmap

- [x] Step 01: Core foundation (schemas, config, logger, memory)
- [x] Step 02: Implement agents (TrendHunter, ScriptWriter, VisualPlanner, SeoManager, QualityReviewer)
- [x] Step 03: Editorial pipeline orchestrator (build_video_package)
- [x] Step 04: Implement services (Veo, TTS, ffmpeg, YouTube, analytics) + I/O (datastore, exports)
- [x] Step 05: Full production pipeline with human gate (produce_render_publish, tasks)
- [x] **Step 05.5:** Human review console & audit trail (`run.py review`)
- [x] **Step 06-pre:** Provider integration & live test (LLM router, Veo wiring)
- [x] **Step 06-fullrun:** First playable build (real MP4/WAV, LLM integration, end-to-end test)
- [x] **Step 07:** Real generation pass (Veo API, TTS API, structured LLM, script audit trail)
- [x] **Step 07.2:** Creator-grade quality pass (HD TTS, multi-tier video, AI thumbnails, quality tracking)
- [x] **Step 07.3:** Script review gate + Sora 2 integration (2-gate workflow, scene sync, cost optimization)
- [x] **Step 07.4:** Asset organization system (per-video isolated directories, AssetPaths schema, scalable multi-video generation)
- [x] **Step 07.5:** Format engine - cross-vertical series system (intro/outro caching, segment structure, YAML templates, works on ANY vertical)
- [x] **Step 08:** Multi-workspace system (workspace isolation, unified CLI, workspace filtering, cross-channel management)
- [ ] **Step 09:** Scheduler automation (APScheduler, per-workspace task scheduling)
- [ ] **Step 10:** Analytics feedback loop and continuous improvement
- [ ] **Step 11:** Quality improvements and testing

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
