# Sub-Agent Development System

## Overview

The yt_autopilot project uses **5 specialized sub-agents** to accelerate development and maintain architectural consistency. Each sub-agent is a Claude Code development assistant with deep expertise in a specific domain of the codebase.

**Purpose**: These sub-agents help YOU (the developer) write better code faster, not to run the YouTube automation system itself.

## Quick Start

When working on a feature, call the appropriate sub-agent using slash commands:

```bash
# Working on AI agent logic?
/ai-strategist Enhance ScriptWriter to generate better viral hooks

# Integrating video APIs?
/video-engineer Add Google Veo as fallback for Sora 2

# Optimizing workflows?
/orchestrator Implement retry logic for failed video generation

# Working with data?
/data-analyst Add TikTok trends as new source

# Modifying schemas or configs?
/architect Add narrator_persona field to ScriptCandidate schema
```

---

## The 5 Sub-Agents

### 🤖 1. AI Content Strategist (`/ai-strategist`)

**Expert in**: AI agents, LLM integration, content strategy

**Domain**:
- `/yt_autopilot/agents/` - TrendHunter, ScriptWriter, VisualPlanner, SeoManager, QualityReviewer
- `/yt_autopilot/services/llm_router.py` - Multi-provider LLM orchestration

**Use for**:
- Implementing/enhancing AI agent logic
- Prompt engineering and LLM integration
- Content strategy (viral hooks, SEO, compliance)
- Pure function design (agents must be side-effect free)

**Example Tasks**:
- "Add semantic duplicate detection to TrendHunter"
- "Improve script hook generation in ScriptWriter"
- "Implement character consistency tracking in VisualPlanner"
- "Add profanity filter to QualityReviewer"

---

### 🎬 2. Video Production Engineer (`/video-engineer`)

**Expert in**: Video/audio generation, ffmpeg, multimedia processing

**Domain**:
- `/yt_autopilot/services/` - Video gen, TTS, thumbnail, assembly services
- `/yt_autopilot/core/asset_manager.py` - Asset organization

**Use for**:
- Integrating video generation APIs (Sora 2, Veo, etc.)
- TTS provider integration and voice customization
- Ffmpeg operations (concatenation, audio sync, filters)
- Asset management (file organization, path tracking)

**Example Tasks**:
- "Integrate Google Veo API as Sora fallback"
- "Add support for 9:16 aspect ratio videos (YouTube Shorts)"
- "Implement audio normalization in ffmpeg pipeline"
- "Create thumbnail generator with custom fonts"

---

### 🔀 3. Pipeline Orchestrator (`/orchestrator`)

**Expert in**: Workflow coordination, state machines, error handling

**Domain**:
- `/yt_autopilot/pipeline/` - Editorial pipeline, production workflow, task scheduler
- `/yt_autopilot/io/datastore.py` (read for state management)

**Use for**:
- Coordinating multi-agent workflows
- Managing production state transitions (4 states, 2-gate review)
- Implementing retry logic and error handling
- Optimizing execution order (parallel vs sequential)

**Example Tasks**:
- "Add automatic retry for failed API calls (3 attempts, exponential backoff)"
- "Parallelize scene generation (generate all scenes concurrently)"
- "Implement resume-from-failure checkpoint system"
- "Add cost estimation before asset generation"

---

### 📊 4. Data & Analytics Specialist (`/data-analyst`)

**Expert in**: Datastore, trend detection, performance analytics

**Domain**:
- `/yt_autopilot/io/` - JSONL datastore, exports, reports
- `/yt_autopilot/core/workspace_manager.py` - Multi-workspace system
- Trend sources (Reddit, HN, YouTube, custom channels)

**Use for**:
- JSONL datastore queries and optimization
- Workspace management and isolation
- Trend detection and scoring algorithms
- Performance analytics and learning loops

**Example Tasks**:
- "Integrate TikTok trends API as new source"
- "Optimize datastore queries with in-memory cache"
- "Implement learning loop (performance-aware topic selection)"
- "Export scripts to CSV for external review"

---

### 🛠️ 5. Schema & Integration Architect (`/architect`)

**Expert in**: Pydantic schemas, configuration, API clients

**Domain**:
- `/yt_autopilot/core/schemas.py` - All Pydantic data models
- `/yt_autopilot/core/config.py` - Configuration system
- External API clients (YouTube, Reddit, HN)

**Use for**:
- Schema design and evolution (Pydantic models)
- Configuration management (environment variables, workspace configs)
- External API integration (OAuth, rate limiting)
- Schema migrations (backward compatibility)

**Example Tasks**:
- "Add character_consistency field to VisualPlan schema"
- "Implement YouTube Analytics API integration"
- "Create migration script for legacy datastore records"
- "Add OAuth flow for Google Drive integration"

---

## Routing Guide: Which Sub-Agent for Which Task?

### By File Path

```
/yt_autopilot/agents/          → /ai-strategist
/yt_autopilot/services/llm_*   → /ai-strategist

/yt_autopilot/services/video_* → /video-engineer
/yt_autopilot/services/tts_*   → /video-engineer
/yt_autopilot/services/*_assemble* → /video-engineer

/yt_autopilot/pipeline/        → /orchestrator

/yt_autopilot/io/              → /data-analyst
/yt_autopilot/services/*_trends* → /data-analyst

/yt_autopilot/core/schemas.py  → /architect
/yt_autopilot/core/config.py   → /architect
```

### By Task Type

| Task Description | Sub-Agent |
|------------------|-----------|
| "Improve content quality/hooks/SEO" | `/ai-strategist` |
| "Add LLM provider" | `/ai-strategist` |
| "Implement compliance check" | `/ai-strategist` |
| "Integrate video generation API" | `/video-engineer` |
| "Optimize ffmpeg operations" | `/video-engineer` |
| "Add TTS voice options" | `/video-engineer` |
| "Fix workflow/state machine" | `/orchestrator` |
| "Add retry logic" | `/orchestrator` |
| "Optimize pipeline performance" | `/orchestrator` |
| "Add trend source" | `/data-analyst` |
| "Implement analytics" | `/data-analyst` |
| "Optimize datastore queries" | `/data-analyst` |
| "Add schema field" | `/architect` |
| "Integrate external API" | `/architect` |
| "Migrate data format" | `/architect` |

---

## Multi-Agent Collaboration

Some complex features require multiple sub-agents working together. Call them sequentially:

### Example 1: Add Narrator Persona Feature

```bash
# Step 1: Update schema (foundation)
/architect Add narrator_persona field to ScriptCandidate schema

# Step 2: Implement agent logic (intelligence)
/ai-strategist Implement narrator persona selection in ScriptWriter

# Step 3: Integrate into pipeline (coordination)
/orchestrator Update pipeline to pass narrator persona preferences
```

### Example 2: Optimize Video Generation Costs

```bash
# Step 1: Track cost metrics (data)
/data-analyst Add cost tracking per video provider

# Step 2: Implement smart fallback (production)
/video-engineer Implement cost-aware multi-tier fallback (Sora → Veo → placeholder)

# Step 3: Integrate into workflow (orchestration)
/orchestrator Add cost estimation before generation, abort if over budget
```

### Example 3: Implement Learning Loop

```bash
# Step 1: Track performance (analytics)
/data-analyst Implement performance tracking (views, engagement per topic)

# Step 2: Update selection logic (intelligence)
/ai-strategist Enhance TrendHunter to prioritize topics similar to top performers

# Step 3: Coordinate feedback loop (workflow)
/orchestrator Sync YouTube analytics daily, trigger re-training
```

---

## Architectural Rules (CRITICAL)

All sub-agents enforce the **strict layering architecture**:

```
┌─────────────────────────────────────┐
│ core/       → imports NOTHING       │ ← Foundation
├─────────────────────────────────────┤
│ agents/     → imports ONLY core/    │ ← Intelligence
│ services/   → imports ONLY core/    │ ← Integration
│ io/         → imports ONLY core/    │ ← Storage
├─────────────────────────────────────┤
│ pipeline/   → imports ALL LAYERS    │ ← Orchestration
└─────────────────────────────────────┘
```

### Layer Responsibilities

- **`core/`** - Schemas, config, logging (no business logic)
- **`agents/`** - Pure functions, AI editorial intelligence (no I/O, no API calls)
- **`services/`** - External integrations (video APIs, TTS, trends)
- **`io/`** - Data persistence (JSONL datastore, exports)
- **`pipeline/`** - Workflow orchestration (only layer that can import all others)

### Critical Constraints

1. **Agents MUST be pure functions** - No side effects, no API calls
2. **Services MUST implement graceful fallbacks** - System works with 0-3 API providers
3. **Pipeline is the ONLY layer that calls LLMs** - Passes results to agents for validation
4. **No automatic YouTube uploads** - Always require human approval (2-gate review)

---

## Benefits of Sub-Agent System

### 1. Specialized Expertise
Each sub-agent develops deep knowledge in its domain:
- `/ai-strategist` knows all agent patterns and LLM best practices
- `/video-engineer` understands ffmpeg quirks and provider APIs
- `/orchestrator` sees the big picture of data flow
- `/data-analyst` optimizes queries and trend scoring
- `/architect` enforces architectural purity

### 2. Faster Development
Sub-agents load only relevant context:
- No need to understand all 12,300 LOC
- Focused on 1,500-2,500 LOC per domain
- 40-60% faster iteration cycles

### 3. Consistent Patterns
Sub-agents maintain domain-specific conventions:
- Pure function design in agents
- Graceful fallback chains in services
- Atomic state transitions in pipeline
- Workspace isolation in datastore
- Backward compatibility in schemas

### 4. Architectural Governance
Sub-agents prevent common mistakes:
- `/ai-strategist` blocks service imports in agents
- `/video-engineer` ensures all providers have fallbacks
- `/orchestrator` validates state transitions
- `/data-analyst` enforces workspace boundaries
- `/architect` checks `core/` imports nothing

### 5. Knowledge Accumulation
Sub-agents learn over time:
- Pattern recognition (what works, what doesn't)
- Trade-off awareness (cost vs quality, speed vs reliability)
- Edge case handling (API quirks, data migrations)

---

## When NOT to Use Sub-Agents

Use main Claude Code for:
- **Simple file reads** - Just reading code to understand
- **Documentation questions** - "How does X work?"
- **Quick fixes** - Single-line changes, typos
- **Running tests** - Executing pytest, bash commands
- **CLI operations** - Git commits, deployments

Use sub-agents for:
- **Feature implementation** - New capabilities requiring domain knowledge
- **Complex refactoring** - Multi-file changes with architectural impact
- **API integration** - New providers, external services
- **Performance optimization** - Domain-specific bottleneck analysis
- **Schema evolution** - Adding fields, migrations

---

## Testing Sub-Agents

Each sub-agent has example tasks to verify it works:

```bash
# Test AI Content Strategist
/ai-strategist Read visual_planner.py and explain character consistency system

# Test Video Production Engineer
/video-engineer Explain the video assembly ffmpeg pipeline in video_assemble_service.py

# Test Pipeline Orchestrator
/orchestrator Explain the 2-gate review workflow in produce_render_publish.py

# Test Data & Analytics Specialist
/data-analyst Show me how workspace isolation is enforced in datastore queries

# Test Schema & Integration Architect
/architect List all Pydantic schemas in schemas.py and their relationships
```

---

## Troubleshooting

### Sub-Agent Not Loading
- Check file exists: `.claude/commands/{sub-agent-name}.md`
- Restart Claude Code CLI
- Try full command: `/ai-strategist` not `ai-strategist`

### Sub-Agent Violates Architecture
- Report issue: Sub-agents should enforce layer rules
- Example: If `/ai-strategist` suggests importing from `services/`, this is a bug

### Not Sure Which Sub-Agent to Use
- Start with task description, main Claude will route
- Or refer to "Routing Guide" section above
- Multi-agent collaboration is OK for complex features

### Sub-Agent Doesn't Understand Context
- Provide file paths: "Look at yt_autopilot/agents/script_writer.py"
- Explain goal: "I want to add X because Y"
- Reference existing patterns: "Similar to how TrendHunter does Z"

---

## Sub-Agent Maintenance

As the codebase evolves:

1. **Update sub-agent prompts** (`.claude/commands/*.md`)
   - Add new file paths when new modules added
   - Update LOC counts if significantly changed
   - Add new example tasks for new capabilities

2. **Update this guide** (`docs/SUB_AGENTS.md`)
   - Add new routing rules for new features
   - Update multi-agent collaboration examples
   - Document new architectural patterns

3. **Test after major refactoring**
   - Ensure sub-agents still understand structure
   - Verify routing guide is still accurate
   - Update if layer responsibilities change

---

## Advanced: Creating New Sub-Agents

If the project grows significantly, consider adding specialized sub-agents:

**Potential Future Sub-Agents**:
- `/testing-specialist` - Test generation, coverage analysis, mocking
- `/performance-optimizer` - Profiling, bottleneck analysis, caching
- `/security-auditor` - API key management, data sanitization, compliance
- `/deployment-engineer` - Docker, CI/CD, cloud infrastructure

**Guidelines for New Sub-Agents**:
1. Must have distinct domain (not overlap with existing 5)
2. Should cover 10%+ of development work
3. Maps to architectural boundaries or technical specialization
4. Clear routing criteria (file paths, task types)

---

## Summary

The sub-agent system accelerates yt_autopilot development by:

1. **Distributing expertise** - 5 specialists vs 1 generalist
2. **Reducing cognitive load** - Focus on 1,500 LOC vs 12,300 LOC
3. **Enforcing architecture** - Specialists know the rules
4. **Accumulating knowledge** - Patterns preserved over time
5. **Enabling parallelism** - Multiple features, multiple sub-agents

**Remember**: Sub-agents help YOU code better. They're development assistants, not runtime components.

---

## Quick Reference Card

```
Task Type                           Sub-Agent
─────────────────────────────────────────────────────────
AI/LLM/Content Strategy          → /ai-strategist
Video/Audio/Multimedia           → /video-engineer
Workflow/State/Orchestration     → /orchestrator
Data/Trends/Analytics            → /data-analyst
Schemas/Config/APIs              → /architect

Architecture Layer                  Sub-Agent
─────────────────────────────────────────────────────────
agents/                          → /ai-strategist
services/ (media)                → /video-engineer
services/ (trends)               → /data-analyst
pipeline/                        → /orchestrator
io/                              → /data-analyst
core/                            → /architect
```

**When in doubt**: Describe your task to main Claude Code, it will route to the right specialist.

Happy coding! 🚀
