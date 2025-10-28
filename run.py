#!/usr/bin/env python3
"""
yt_autopilot CLI - Main entry point for workspace-based video generation and review

Multi-workspace YouTube automation system that supports multiple channels
with different verticals (tech, fitness, finance, gaming).

Usage:
    # Workspace management
    python run.py workspace list
    python run.py workspace info
    python run.py workspace switch <workspace_id>
    python run.py workspace create

    # Trend detection (preview only)
    python run.py trends [--top N] [--source SOURCE]

    # Video generation
    python run.py generate [--use-llm-curation]

    # Script review (Gate 1)
    python run.py review scripts
    python run.py review show-script <script_id>
    python run.py review approve-script <script_id> --approved-by "name"

    # Video review (Gate 2)
    python run.py review stats
    python run.py review list
    python run.py review show <video_id>
    python run.py review publish <video_id> --approved-by "name"

Examples:
    # Morning: switch to tech channel and generate video
    python run.py workspace switch tech_ai_creator
    python run.py generate

    # Review and approve script
    python run.py review scripts
    python run.py review show-script abc123-script-id
    python run.py review approve-script abc123-script-id --approved-by "dan@company"

    # Review and publish video
    python run.py review list
    python run.py review show 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
    python run.py review publish 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d --approved-by "dan@company"
"""

import sys
import argparse
from pathlib import Path
import warnings
import json

# Suppress urllib3 OpenSSL warning
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from yt_autopilot.core.workspace_manager import (
    list_workspaces,
    get_active_workspace,
    get_active_workspace_id,
    switch_workspace,
    create_workspace,
    get_workspace_info
)
from yt_autopilot.core.config import get_vertical_configs, get_vertical_config, get_config
from yt_autopilot.pipeline.build_video_package import build_video_package
from yt_autopilot.io.datastore import (
    list_pending_review,
    get_draft_package,
    list_pending_script_review,
    get_script_draft,
    approve_script_for_generation
)
from yt_autopilot.pipeline.produce_render_publish import publish_after_approval


# ============================================================================
# TRENDS COMMAND
# ============================================================================

def cmd_trends(args):
    """Show trending topics for active workspace without generating video"""
    from yt_autopilot.core.logger import logger
    from yt_autopilot.services.trend_source import fetch_trends
    from yt_autopilot.agents.trend_hunter import generate_video_plan

    try:
        workspace = get_active_workspace()
        workspace_id = workspace['workspace_id']
        workspace_name = workspace['workspace_name']
        vertical_id = workspace.get('vertical_id', 'general')

        # Get vertical config
        vertical_config = get_vertical_config(vertical_id)
        if not vertical_config:
            print(f"\n⚠️  Unknown vertical: {vertical_id}")
            return

        cpm = vertical_config.get('cpm_baseline', 10.0)
        channels_count = len(vertical_config.get('youtube_channels', []))
        subreddits_count = len(vertical_config.get('reddit_subreddits', []))
        keywords_count = len(vertical_config.get('target_keywords', []))

        print()
        print("━" * 60)
        print(f" TREND DETECTION: {workspace_id}")
        print("━" * 60)
        print(f" Workspace: {workspace_name} ({vertical_id})")
        print(f" Channels: {channels_count} | Subreddits: {subreddits_count} | Keywords: {keywords_count}")
        print(f" CPM Baseline: ${cpm}")
        print("━" * 60)
        print()

        print("🔍 Fetching trends...")

        # Fetch trends
        trends = fetch_trends(
            workspace_id=workspace_id,
            vertical_id=vertical_id,
            limit=args.top
        )

        if not trends:
            print()
            print("⚠️  No trends found")
            print()
            print("Possible reasons:")
            print("  - No API keys configured (.env)")
            print("  - All trends filtered out (banned topics, duplicates)")
            print("  - API rate limits reached")
            print()
            return

        # Filter by source if specified
        if args.source:
            trends = [t for t in trends if args.source.lower() in t.source.lower()]
            if not trends:
                print(f"\n⚠️  No trends found for source: {args.source}\n")
                return

        print(f"📊 Top {len(trends)} Trending Topics:\n")

        # Display trends
        for i, trend in enumerate(trends, 1):
            # Calculate score manually (simplified version from trend_hunter)
            score = trend.momentum_score + (trend.cpm_estimate / 50.0) * 0.3

            print(f"{i}. [{score:.2f}] {trend.keyword}")
            print(f"   Source: {trend.source}")
            print(f"   CPM: ${trend.cpm_estimate:.1f} | Competition: {trend.competition_level} | Virality: {trend.virality_score:.2f}")
            print(f"   Why: {trend.why_hot[:80]}...")
            print()

        print("━" * 60)
        print("💡 Next steps:")
        print(f"  - Generate video: python run.py generate")
        print(f"  - See more: python run.py trends --top {args.top * 2}")
        if not args.source:
            print(f"  - Filter source: python run.py trends --source reddit")
        print("━" * 60)
        print()

    except RuntimeError as e:
        print(f"\n⚠️  Error: {e}\n")
        print("Run 'python run.py workspace switch <id>' to select a workspace")
        print()
    except Exception as e:
        logger.error(f"Trend detection failed: {e}")
        print(f"\n⚠️  Trend detection failed: {e}\n")


# ============================================================================
# WORKSPACE COMMANDS
# ============================================================================

def cmd_workspace_list(args):
    """List all available workspaces"""
    workspaces = list_workspaces()
    active_id = get_active_workspace_id()

    print()
    print("Available workspaces:")
    print()

    if not workspaces:
        print("  (No workspaces found)")
        print()
        print("  Create your first workspace with: python run.py workspace create")
        return

    for ws in workspaces:
        is_active = " (ACTIVE)" if ws['workspace_id'] == active_id else ""
        marker = "→" if ws['workspace_id'] == active_id else " "

        # Get vertical info
        v_config = get_vertical_config(ws['vertical_id'])
        cpm = f"${v_config['cpm_baseline']:.0f}" if v_config else "?"

        print(f"  {marker} {ws['workspace_id']:<25} {ws['workspace_name']:<30} (CPM: {cpm}){is_active}")

    print()


def cmd_workspace_info(args):
    """Show current workspace information"""
    try:
        workspace = get_active_workspace()
        info = get_workspace_info(workspace['workspace_id'])
        print(info)
    except RuntimeError as e:
        print(f"\n⚠️  {e}\n")
        cmd_workspace_list(args)


def cmd_workspace_switch(args):
    """Switch to different workspace"""
    try:
        workspace = switch_workspace(args.workspace_id)

        print()
        print(f"✓ Switched to workspace: {workspace['workspace_name']}")
        print()

        # Show workspace info
        info = get_workspace_info(args.workspace_id)
        print(info)

    except FileNotFoundError as e:
        print(f"\n❌ Error: {e}\n")
        cmd_workspace_list(args)
        sys.exit(1)


def cmd_workspace_create(args):
    """Interactive workspace creation"""
    print()
    print("=" * 70)
    print("CREATE NEW WORKSPACE")
    print("=" * 70)
    print()

    # Get workspace ID
    workspace_id = input("Workspace ID (e.g., 'my_cooking_channel'): ").strip()
    if not workspace_id:
        print("❌ Workspace ID cannot be empty")
        sys.exit(1)

    # Get workspace name
    workspace_name = input("Workspace name (e.g., 'My Cooking Channel'): ").strip()
    if not workspace_name:
        workspace_name = workspace_id.replace("_", " ").title()

    # Select vertical
    print()
    print("Select vertical:")
    verticals = get_vertical_configs()
    vertical_list = list(verticals.items())

    for i, (v_id, v_config) in enumerate(vertical_list, 1):
        cpm = v_config['cpm_baseline']
        print(f"  {i}. {v_id:<15} (CPM: ${cpm:.1f})")

    print()
    vertical_choice = input(f"Select vertical (1-{len(vertical_list)}): ").strip()

    try:
        vertical_idx = int(vertical_choice) - 1
        if vertical_idx < 0 or vertical_idx >= len(vertical_list):
            raise ValueError()
        vertical_id = vertical_list[vertical_idx][0]
    except (ValueError, IndexError):
        print("❌ Invalid selection")
        sys.exit(1)

    # Get brand tone
    print()
    brand_tone = input("Brand tone (e.g., 'Direct, positive, educational'): ").strip()
    if not brand_tone:
        brand_tone = "Direct, positive, educational"

    # Create workspace
    try:
        config = create_workspace(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            vertical_id=vertical_id,
            brand_tone=brand_tone
        )

        print()
        print(f"✓ Created workspace: {workspace_name}")
        print(f"  ID: {workspace_id}")
        print(f"  Vertical: {vertical_id}")
        print()
        print(f"Switch to this workspace with:")
        print(f"  python run.py workspace switch {workspace_id}")
        print()

    except ValueError as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


# ============================================================================
# GENERATE COMMANDS
# ============================================================================

def cmd_generate(args):
    """Generate video using active workspace"""
    try:
        workspace = get_active_workspace()

        print()
        print("=" * 70)
        print(f"GENERATING VIDEO - Workspace: {workspace['workspace_name']}")
        print("=" * 70)
        print(f"Vertical: {workspace['vertical_id']}")
        print(f"Brand tone: {workspace.get('brand_tone', 'Not set')[:60]}...")
        print("=" * 70)
        print()

        # Build video package (workspace system handles memory management)
        package = build_video_package(
            workspace_id=workspace['workspace_id'],
            use_real_trends=True,
            use_llm_curation=args.use_llm_curation
        )

        print()
        print("=" * 70)
        print("VIDEO GENERATION COMPLETE")
        print("=" * 70)
        print(f"Status: {package.status}")
        print(f"Title: {package.video_plan.working_title}")
        print("=" * 70)
        print()

    except RuntimeError as e:
        print(f"\n⚠️  {e}\n")
        cmd_workspace_list(args)
        sys.exit(1)


# ============================================================================
# REVIEW COMMANDS - GATE 1 (Script Review)
# ============================================================================

def cmd_review_scripts(args):
    """List all scripts pending human review (Gate 1)."""
    # Get workspace filter
    if args.all_workspaces:
        workspace_id = None
        workspace_label = "all workspaces"
    else:
        try:
            workspace = get_active_workspace()
            workspace_id = workspace['workspace_id']
            workspace_label = f"workspace: {workspace['workspace_name']}"
        except RuntimeError:
            print("\n⚠️  No active workspace found!")
            print("Switch workspace with: python run.py workspace switch <id>")
            print("Or use --all-workspaces to see all scripts\n")
            return

    print("=" * 70)
    print("SCRIPT REVIEW QUEUE (GATE 1 - cheap)")
    print("=" * 70)
    print(f"Showing scripts for: {workspace_label}")
    print()

    pending = list_pending_script_review(workspace_id=workspace_id)

    if not pending:
        print("No scripts pending review.")
        print()
        print("TIP: Generate a new script draft with:")
        print("  python run.py generate")
        print()
        return

    print(f"Found {len(pending)} script(s) pending review:")
    print()

    for i, script in enumerate(pending, 1):
        print(f"[{i}] {script['production_state']}")
        print(f"  script_internal_id: {script['script_internal_id']}")
        if args.all_workspaces and script.get('workspace_id'):
            print(f"  workspace: {script['workspace_id']}")

        # Extract key info from video_plan
        video_plan = script.get('video_plan', {})
        print(f"  topic: {video_plan.get('working_title', 'N/A')}")

        # Extract script preview
        script_obj = script.get('script', {})
        hook = script_obj.get('hook', '')
        if hook:
            hook_preview = hook[:80] + "..." if len(hook) > 80 else hook
            print(f"  hook: {hook_preview}")

        # Scene count
        visuals = script.get('visuals', {})
        scene_count = len(visuals.get('scenes', []))
        print(f"  scenes: {scene_count}")

        # Timing
        print(f"  saved_at: {script.get('saved_at', 'N/A')}")
        print()

    print("=" * 70)
    print("NEXT STEPS:")
    print(f"  1. Review script details: python run.py review show-script <script_id>")
    print(f"  2. Approve script: python run.py review approve-script <script_id> --approved-by \"you@company\"")
    print("=" * 70)


def cmd_review_show_script(args):
    """Show detailed script information in 2-level format (Gate 1)."""
    script_id = args.script_id

    print("=" * 70)
    print("SCRIPT DRAFT DETAILS (GATE 1)")
    print("=" * 70)
    print()

    draft = get_script_draft(script_id)

    if draft is None:
        print(f"ERROR: Script draft not found: {script_id}")
        print()
        sys.exit(1)

    # Extract components
    video_plan = draft.get('video_plan', {})
    script = draft.get('script', {})
    visuals = draft.get('visuals', {})
    publishing = draft.get('publishing', {})

    print(f"SCRIPT INTERNAL ID: {draft.get('script_internal_id')}")
    print(f"Status: {draft.get('production_state')}")
    print(f"Saved at: {draft.get('saved_at')}")
    print()

    # ========================================================================
    # LEVEL 1: CONCEPT SUMMARY (high-level overview)
    # ========================================================================
    print("=" * 70)
    print("LEVEL 1: CONCEPT SUMMARY")
    print("=" * 70)
    print()

    print(f"TOPIC: {video_plan.get('working_title', 'N/A')}")
    print()

    print(f"TARGET AUDIENCE: {video_plan.get('target_audience', 'N/A')}")
    print()

    print(f"STRATEGIC ANGLE:")
    print(f"  {video_plan.get('strategic_angle', 'N/A')}")
    print()

    print(f"HOOK (first 3 seconds):")
    print(f"  \"{script.get('hook', 'N/A')}\"")
    print()

    print(f"CONTENT BULLETS:")
    bullets = script.get('bullets', [])
    for i, bullet in enumerate(bullets, 1):
        print(f"  {i}. {bullet}")
    print()

    print(f"CALL-TO-ACTION:")
    print(f"  \"{script.get('outro_cta', 'N/A')}\"")
    print()

    # Calculate total duration
    scene_voiceover_map = script.get('scene_voiceover_map', [])
    total_duration = sum(s.get('est_duration_seconds', 0) for s in scene_voiceover_map)
    print(f"ESTIMATED DURATION: ~{total_duration} seconds ({len(scene_voiceover_map)} scenes)")
    print()

    # ========================================================================
    # LEVEL 2: DETAILED BREAKDOWN (scene-by-scene)
    # ========================================================================
    print("=" * 70)
    print("LEVEL 2: DETAILED BREAKDOWN (Scene-by-Scene)")
    print("=" * 70)
    print()

    scenes = visuals.get('scenes', [])

    if not scenes:
        print("  (No scenes available)")
        print()
    else:
        for scene in scenes:
            scene_id = scene.get('scene_id')
            voiceover = scene.get('voiceover_text', '')
            veo_prompt = scene.get('prompt_for_veo', '')
            duration = scene.get('est_duration_seconds', 0)

            print(f"SCENE {scene_id} (~{duration}s)")
            print(f"  Voiceover:")
            print(f"    \"{voiceover}\"")
            print()
            print(f"  Visual Prompt (Veo):")
            # Truncate long prompts
            if len(veo_prompt) > 200:
                print(f"    {veo_prompt[:200]}...")
            else:
                print(f"    {veo_prompt}")
            print()

    # ========================================================================
    # METADATA
    # ========================================================================
    print("=" * 70)
    print("PUBLISHING METADATA")
    print("=" * 70)
    print()

    print(f"PROPOSED TITLE:")
    print(f"  {publishing.get('final_title', 'N/A')}")
    print()

    print(f"PROPOSED DESCRIPTION:")
    description = publishing.get('description', '')
    if len(description) > 300:
        print(f"  {description[:300]}...")
    else:
        print(f"  {description}")
    print()

    print(f"PROPOSED TAGS:")
    tags = publishing.get('tags', [])
    print(f"  {', '.join(tags)}")
    print()

    print(f"SUGGESTED PUBLISH AT:")
    print(f"  {draft.get('proposed_publish_at', 'N/A')}")
    print()

    # ========================================================================
    # APPROVAL INSTRUCTIONS
    # ========================================================================
    print("=" * 70)
    print("TO APPROVE THIS SCRIPT AND TRIGGER ASSET GENERATION:")
    print(f"  python run.py review approve-script {script_id} --approved-by \"your@email\"")
    print()
    print("WARNING: Approval will trigger expensive API calls:")
    print("  - Sora 2 video generation (~$$$)")
    print("  - OpenAI TTS audio generation (~$$)")
    print("  - DALL-E 3 thumbnail generation (~$)")
    print("  Total estimated cost: ~$5-10 USD per video")
    print("=" * 70)


def cmd_review_approve_script(args):
    """Approve script and trigger asset generation (Gate 1 → Gate 2)."""
    script_id = args.script_id
    approved_by = args.approved_by

    if not approved_by:
        print("ERROR: --approved-by is required")
        print("Example: python run.py review approve-script <script_id> --approved-by \"dan@company\"")
        sys.exit(1)

    print("=" * 70)
    print("APPROVING SCRIPT FOR ASSET GENERATION")
    print("=" * 70)
    print()
    print(f"Script ID: {script_id}")
    print(f"Approved by: {approved_by}")
    print()

    # Verify script exists and is in correct state
    draft = get_script_draft(script_id)
    if draft is None:
        print("ERROR: Script draft not found")
        sys.exit(1)

    current_state = draft.get('production_state')
    if current_state != 'SCRIPT_PENDING_REVIEW':
        print(f"ERROR: Script is not pending review (current state: {current_state})")
        print(f"Only scripts in SCRIPT_PENDING_REVIEW state can be approved.")
        sys.exit(1)

    print("Marking script as READY_FOR_GENERATION...")
    print()

    try:
        approve_script_for_generation(script_id, approved_by)

        print("=" * 70)
        print("✓ SUCCESS: Script approved")
        print("=" * 70)
        print(f"Script ID: {script_id}")
        print(f"New state: READY_FOR_GENERATION")
        print(f"Approved by: {approved_by}")
        print()
        print("NEXT STEPS:")
        print("  1. Trigger asset generation:")
        print("       from yt_autopilot.pipeline.produce_render_publish import produce_render_assets")
        print(f"       produce_render_assets(script_internal_id='{script_id}')")
        print()
        print("  2. After generation completes, review the video:")
        print("       python run.py review list")
        print("       python run.py review show <video_id>")
        print()
        print("  3. If satisfied, publish to YouTube:")
        print("       python run.py review publish <video_id> --approved-by \"your@email\"")
        print("=" * 70)

    except Exception as e:
        print("=" * 70)
        print("✗ ERROR: Script approval failed")
        print("=" * 70)
        print(f"Error: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# REVIEW COMMANDS - GATE 2 (Video Review)
# ============================================================================

def cmd_review_stats(args):
    """Show datastore statistics and state distribution."""
    print("=" * 70)
    print("DATASTORE STATISTICS")
    print("=" * 70)
    print()

    config = get_config()
    datastore_path = config["PROJECT_ROOT"] / "data" / "records.jsonl"

    if not datastore_path.exists():
        print("No datastore file found.")
        print(f"Expected: {datastore_path}")
        print()
        return

    # Analyze records
    state_counts = {}
    legacy_states = []
    total_records = 0

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            total_records += 1
            record = json.loads(line.strip())
            state = record.get("production_state", "UNKNOWN")

            state_counts[state] = state_counts.get(state, 0) + 1

            # Track legacy states
            if state == "HUMAN_REVIEW_PENDING":
                legacy_states.append(record)

    print(f"Total records: {total_records}")
    print()

    print("RECORDS BY STATE:")
    print("-" * 70)

    # Sort states by count (descending)
    sorted_states = sorted(state_counts.items(), key=lambda x: x[1], reverse=True)

    for state, count in sorted_states:
        marker = ""
        if state == "HUMAN_REVIEW_PENDING":
            marker = " ⚠️  LEGACY STATE"
        elif state == "VIDEO_PENDING_REVIEW":
            marker = " ✓ Current (Step 07.3)"
        elif state == "SCRIPT_PENDING_REVIEW":
            marker = " ✓ Gate 1"
        elif state == "READY_FOR_GENERATION":
            marker = " → Ready for assets"
        elif state == "SCHEDULED_ON_YOUTUBE":
            marker = " ✓ Published"

        print(f"  {state}: {count}{marker}")

    print()

    # Legacy state warnings
    if legacy_states:
        print("=" * 70)
        print("⚠️  LEGACY STATES DETECTED")
        print("=" * 70)
        print()
        print(f"Found {len(legacy_states)} record(s) with legacy state HUMAN_REVIEW_PENDING")
        print()
        print("These should be migrated to VIDEO_PENDING_REVIEW for consistency.")
        print()

    # Cleanup suggestions
    orphan_scripts = state_counts.get("READY_FOR_GENERATION", 0)
    if orphan_scripts > 0:
        print("=" * 70)
        print("💡 CLEANUP SUGGESTIONS")
        print("=" * 70)
        print()
        print(f"Found {orphan_scripts} script(s) in READY_FOR_GENERATION state.")
        print()
        print("These may be orphaned scripts from previous runs.")
        print()

    print("=" * 70)


def cmd_review_list(args):
    """List all videos pending human review."""
    # Get workspace filter
    if args.all_workspaces:
        workspace_id = None
        workspace_label = "all workspaces"
    else:
        try:
            workspace = get_active_workspace()
            workspace_id = workspace['workspace_id']
            workspace_label = f"workspace: {workspace['workspace_name']}"
        except RuntimeError:
            print("\n⚠️  No active workspace found!")
            print("Switch workspace with: python run.py workspace switch <id>")
            print("Or use --all-workspaces to see all videos\n")
            return

    print("=" * 70)
    print("PENDING REVIEW QUEUE (GATE 2)")
    print("=" * 70)
    print(f"Showing videos for: {workspace_label}")
    print()

    pending = list_pending_review(workspace_id=workspace_id)

    if not pending:
        print("No videos pending review.")
        print()
        return

    print(f"Found {len(pending)} video(s) pending review:")
    print()

    for i, video in enumerate(pending, 1):
        print(f"[{i}] {video['production_state']}")
        print(f"  video_internal_id: {video['video_internal_id']}")
        if args.all_workspaces and video.get('workspace_id'):
            print(f"  workspace: {video['workspace_id']}")
        print(f"  final_video_path: {video['final_video_path']}")
        print(f"  thumbnail_path: {video['thumbnail_path']}")
        print(f"  proposed_title: {video['proposed_title']}")
        print(f"  suggested_publishAt: {video['suggested_publishAt']}")
        print(f"  saved_at: {video['saved_at']}")
        print()


def cmd_review_show(args):
    """Show detailed information about a specific draft."""
    video_id = args.video_id

    print("=" * 70)
    print("DRAFT PACKAGE DETAILS")
    print("=" * 70)
    print()

    draft = get_draft_package(video_id)

    if draft is None:
        print(f"ERROR: Draft package not found: {video_id}")
        print()
        sys.exit(1)

    files = draft.get("files", {})
    publishing = draft.get("publishing", {})

    print(f"VIDEO INTERNAL ID: {draft.get('video_internal_id')}")
    print(f"Status: {draft.get('production_state')}")
    print()

    print("FILES:")
    print(f"  final_video_path: {files.get('final_video_path')}")
    print(f"  thumbnail_path: {files.get('thumbnail_path')}")
    print(f"  voiceover_path: {files.get('voiceover_path')}")
    print(f"  scene_paths: {len(files.get('scene_paths', []))} scenes")
    print()

    print("PROPOSED TITLE:")
    print(f"  {draft.get('title')}")
    print()

    print("PROPOSED DESCRIPTION:")
    description = publishing.get("description", "")
    # Print first 300 chars of description
    if len(description) > 300:
        print(f"  {description[:300]}...")
    else:
        print(f"  {description}")
    print()

    print("PROPOSED TAGS:")
    tags = publishing.get("tags", [])
    print(f"  {tags}")
    print()

    print("SUGGESTED PUBLISH AT:")
    print(f"  {draft.get('proposed_publish_at')}")
    print()

    print("SAVED AT:")
    print(f"  {draft.get('saved_at')}")
    print()

    # Step 07: Script Audit Trail
    print("SCRIPT AUDIT TRAIL (Step 07):")
    llm_raw = draft.get("llm_raw_script")
    final_script = draft.get("final_script")

    if llm_raw:
        print("  LLM Raw Output:")
        if len(llm_raw) > 400:
            print(f"    {llm_raw[:400]}...")
            print(f"    (Total: {len(llm_raw)} chars)")
        else:
            print(f"    {llm_raw}")
    else:
        print("  LLM Raw Output: (not available)")

    print()

    if final_script:
        print("  Final Validated Script:")
        if len(final_script) > 400:
            print(f"    {final_script[:400]}...")
            print(f"    (Total: {len(final_script)} chars)")
        else:
            print(f"    {final_script}")
    else:
        print("  Final Validated Script: (not available)")

    print()

    # Step 07.2: Creative Quality Check
    print("CREATIVE QUALITY CHECK (Step 07.2):")

    video_provider = draft.get("video_provider_used")
    voice_provider = draft.get("voice_provider_used")
    thumb_provider = draft.get("thumb_provider_used")
    thumbnail_prompt = draft.get("thumbnail_prompt")

    print(f"  Video Provider: {video_provider or '(not available - legacy record)'}")
    print(f"  Voice Provider: {voice_provider or '(not available - legacy record)'}")
    print(f"  Thumbnail Provider: {thumb_provider or '(not available - legacy record)'}")

    if thumbnail_prompt:
        print(f"  Thumbnail Prompt: {thumbnail_prompt[:200]}{'...' if len(thumbnail_prompt) > 200 else ''}")
    else:
        print(f"  Thumbnail Prompt: (not available)")

    print()

    # Quality indicators
    print("  Quality Indicators:")
    real_providers_count = sum([
        1 for p in [video_provider, voice_provider, thumb_provider]
        if p and "FALLBACK" not in p and "PLACEHOLDER" not in p and "SILENT" not in p
    ])
    total_providers = 3
    quality_score = (real_providers_count / total_providers) * 100

    print(f"    Real AI providers used: {real_providers_count}/{total_providers}")
    print(f"    Creator-grade quality: {quality_score:.0f}%")

    if quality_score == 100:
        print(f"    Status: ✓ FULL CREATOR-GRADE QUALITY")
    elif quality_score >= 66:
        print(f"    Status: ~ PARTIAL CREATOR-GRADE (some fallbacks)")
    else:
        print(f"    Status: ⚠ MOSTLY FALLBACKS (check API keys)")

    print()

    print("=" * 70)
    print("To approve and publish this video:")
    print(f"  python run.py review publish {video_id} --approved-by \"your@email\"")
    print("=" * 70)


def cmd_review_publish(args):
    """Publish an approved draft to YouTube."""
    video_id = args.video_id
    approved_by = args.approved_by

    if not approved_by:
        print("ERROR: --approved-by is required")
        print("Example: python run.py review publish <video_id> --approved-by \"dan@company\"")
        sys.exit(1)

    print("=" * 70)
    print("PUBLISHING VIDEO TO YOUTUBE")
    print("=" * 70)
    print()
    print(f"Video ID: {video_id}")
    print(f"Approved by: {approved_by}")
    print()
    print("Uploading to YouTube and scheduling publication...")
    print()

    try:
        result = publish_after_approval(video_id, approved_by)

        if result["status"] == "SCHEDULED":
            print("=" * 70)
            print("✓ SUCCESS: Video scheduled on YouTube")
            print("=" * 70)
            print(f"YouTube Video ID: {result['video_id']}")
            print(f"Publish at: {result['publishAt']}")
            print(f"Title: {result['title']}")
            print(f"Approved by: {result['approved_by']}")
            print(f"Approved at: {result['approved_at_iso']}")
            print("=" * 70)
        elif result["status"] == "ERROR":
            print("=" * 70)
            print("✗ ERROR: Publication failed")
            print("=" * 70)
            print(f"Reason: {result.get('reason')}")
            print("=" * 70)
            sys.exit(1)
        else:
            print(f"Unexpected status: {result['status']}")
            sys.exit(1)

    except Exception as e:
        print("=" * 70)
        print("✗ EXCEPTION: Publication failed")
        print("=" * 70)
        print(f"Error: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ============================================================================
# MAIN ARGPARSE SETUP
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="yt_autopilot - Multi-workspace YouTube automation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Available command groups")

    # ========================================================================
    # WORKSPACE COMMAND GROUP
    # ========================================================================
    workspace_parser = subparsers.add_parser("workspace", help="Workspace management commands")
    workspace_subparsers = workspace_parser.add_subparsers(dest="workspace_command")

    # workspace list
    ws_list = workspace_subparsers.add_parser("list", help="List all available workspaces")
    ws_list.set_defaults(func=cmd_workspace_list)

    # workspace info
    ws_info = workspace_subparsers.add_parser("info", help="Show current workspace information")
    ws_info.set_defaults(func=cmd_workspace_info)

    # workspace switch
    ws_switch = workspace_subparsers.add_parser("switch", help="Switch to a different workspace")
    ws_switch.add_argument("workspace_id", help="Workspace ID to switch to")
    ws_switch.set_defaults(func=cmd_workspace_switch)

    # workspace create
    ws_create = workspace_subparsers.add_parser("create", help="Create a new workspace interactively")
    ws_create.set_defaults(func=cmd_workspace_create)

    # ========================================================================
    # TRENDS COMMAND
    # ========================================================================
    trends_parser = subparsers.add_parser("trends", help="Show trending topics without generating video")
    trends_parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top trends to show (default: 10)"
    )
    trends_parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Filter by source (e.g., reddit, youtube_channel, hackernews)"
    )
    trends_parser.set_defaults(func=cmd_trends)

    # ========================================================================
    # GENERATE COMMAND
    # ========================================================================
    generate_parser = subparsers.add_parser("generate", help="Generate video using active workspace")
    generate_parser.add_argument(
        "--use-llm-curation",
        action="store_true",
        help="Enable LLM curation for trend selection (Phase B)"
    )
    generate_parser.set_defaults(func=cmd_generate)

    # ========================================================================
    # REVIEW COMMAND GROUP
    # ========================================================================
    review_parser = subparsers.add_parser("review", help="Script and video review commands (2-Gate workflow)")
    review_subparsers = review_parser.add_subparsers(dest="review_command")

    # Gate 1: Script review
    r_scripts = review_subparsers.add_parser("scripts", help="[Gate 1] List all scripts pending review")
    r_scripts.add_argument("--all-workspaces", action="store_true", help="Show scripts from all workspaces (default: current workspace only)")
    r_scripts.set_defaults(func=cmd_review_scripts)

    r_show_script = review_subparsers.add_parser("show-script", help="[Gate 1] Show script details in 2-level format")
    r_show_script.add_argument("script_id", help="Script internal ID")
    r_show_script.set_defaults(func=cmd_review_show_script)

    r_approve_script = review_subparsers.add_parser("approve-script", help="[Gate 1] Approve script for asset generation")
    r_approve_script.add_argument("script_id", help="Script internal ID")
    r_approve_script.add_argument("--approved-by", required=True, help="Approver identifier (e.g., dan@company)")
    r_approve_script.set_defaults(func=cmd_review_approve_script)

    # Gate 2: Video review
    r_stats = review_subparsers.add_parser("stats", help="Show datastore statistics and state distribution")
    r_stats.set_defaults(func=cmd_review_stats)

    r_list = review_subparsers.add_parser("list", help="[Gate 2] List all videos pending review")
    r_list.add_argument("--all-workspaces", action="store_true", help="Show videos from all workspaces (default: current workspace only)")
    r_list.set_defaults(func=cmd_review_list)

    r_show = review_subparsers.add_parser("show", help="[Gate 2] Show details of a specific draft")
    r_show.add_argument("video_id", help="Video internal ID")
    r_show.set_defaults(func=cmd_review_show)

    r_publish = review_subparsers.add_parser("publish", help="[Gate 2] Approve and publish a draft to YouTube")
    r_publish.add_argument("video_id", help="Video internal ID")
    r_publish.add_argument("--approved-by", required=True, help="Approver identifier (e.g., dan@company)")
    r_publish.set_defaults(func=cmd_review_publish)

    # ========================================================================
    # PARSE AND EXECUTE
    # ========================================================================
    args = parser.parse_args()

    # Handle no command (default behavior)
    if not args.command:
        try:
            workspace = get_active_workspace()
            cmd_workspace_info(args)
            print()
            print("Run 'python run.py --help' to see available commands")
            print()
        except RuntimeError:
            print()
            print("⚠️  No active workspace found!")
            print()
            cmd_workspace_list(args)
            print()
            print("Run 'python run.py workspace switch <id>' to select a workspace")
            print("Or run 'python run.py workspace create' to create a new one")
            print()
        return

    # Execute command
    if hasattr(args, 'func'):
        args.func(args)
    else:
        # Subcommand group was specified but no subcommand
        if args.command == "workspace":
            workspace_parser.print_help()
        elif args.command == "review":
            review_parser.print_help()
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
