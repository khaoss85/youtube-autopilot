#!/usr/bin/env python3
"""
yt_autopilot CLI - Main entry point for workspace-based video generation and review

Multi-workspace YouTube automation system that supports multiple channels
with different verticals (tech, fitness, finance, gaming).

Usage:
    # Workspace management
    python3 run.py workspace list
    python3 run.py workspace info
    python3 run.py workspace switch <workspace_id>
    python3 run.py workspace create
    python3 run.py workspace reset [--workspace-id ID] [--all] [--dry-run] [--yes]

    # Trend detection (preview only)
    python3 run.py trends [--top N] [--source SOURCE]

    # Video generation
    python3 run.py generate [--use-llm-curation]

    # Script review (Gate 1)
    python3 run.py review scripts [--all-workspaces]
    python3 run.py review show-script <script_id>
    python3 run.py review approve-script <script_id> --approved-by "name"
    python3 run.py review export-visual-deck <script_id>

    # Video review (Gate 2)
    python3 run.py review stats
    python3 run.py review list [--all-workspaces]
    python3 run.py review show <video_id>

    # Note: Current workflow stops at content package export (manual upload to YouTube)
    # Automated upload coming in future release

Examples:
    # Morning: switch to tech channel and generate video
    python3 run.py workspace switch tech_ai_creator
    python3 run.py generate

    # Review and approve script
    python3 run.py review scripts
    python3 run.py review show-script abc123-script-id
    python3 run.py review approve-script abc123-script-id --approved-by "dan@company"

    # Optional: Generate visual deck with DALL-E 3 reference images
    python3 run.py review export-visual-deck abc123-script-id

    # Review video packages (ready for manual upload)
    python3 run.py review list
    python3 run.py review show 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
    # After review: use exported content package for manual video assembly and YouTube upload

    # Cleanup: reset workspace to clear unpublished records
    python3 run.py workspace reset --dry-run  # Preview changes first
    python3 run.py workspace reset --yes      # Execute reset on active workspace
    python3 run.py workspace reset --all      # Reset all workspaces (clears recent_titles)
"""

import sys
import argparse
from pathlib import Path
import warnings
import json
from datetime import datetime, timedelta

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
    approve_script_for_generation,
    save_script_draft
)


# ============================================================================
# TRENDS COMMAND
# ============================================================================

def cmd_trends(args):
    """Show trending topics for active workspace without generating video"""
    from yt_autopilot.core.logger import logger
    from yt_autopilot.services.trend_source import fetch_trends
    from yt_autopilot.agents.trend_hunter import _calculate_priority_score

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

        # Fetch trends (returns all trends from all sources)
        all_trends = fetch_trends(
            vertical_id=vertical_id,
            use_real_apis=True
        )

        if not all_trends:
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
            filtered = [t for t in all_trends if args.source.lower() in t.source.lower()]
            if not filtered:
                print(f"\n⚠️  No trends found for source: {args.source}\n")
                return
            trends = filtered[:args.top]
        else:
            # Limit to top N
            trends = all_trends[:args.top]

        print(f"📊 Top {len(trends)} Trending Topics (from {len(all_trends)} total):\n")

        # Use workspace config as memory for proper scoring
        memory = workspace

        # Display trends with real scores from trend_hunter
        for i, trend in enumerate(trends, 1):
            # Use actual scoring function from trend_hunter
            score = _calculate_priority_score(trend, memory)

            # Show keyword matches if available
            keyword_info = ""
            if hasattr(trend, 'keyword_match_count') and trend.keyword_match_count > 0:
                keyword_info = f" ({trend.keyword_match_count} keywords)"

            print(f"{i}. [{score:.2f}] {trend.keyword}{keyword_info}")
            print(f"   Source: {trend.source}")
            print(f"   CPM: ${trend.cpm_estimate:.1f} | Competition: {trend.competition_level} | Virality: {trend.virality_score:.2f}")
            why_display = trend.why_hot if len(trend.why_hot) <= 200 else trend.why_hot[:200] + "..."
            print(f"   Why: {why_display}")
            print()

        print("━" * 60)
        print("💡 Next steps:")
        print(f"  - Generate video: python3 run.py generate")
        print(f"  - See more: python3 run.py trends --top {args.top * 2}")
        if not args.source:
            print(f"  - Filter source: python3 run.py trends --source reddit")
        print("━" * 60)
        print()

    except RuntimeError as e:
        print(f"\n⚠️  Error: {e}\n")
        print("Run 'python3 run.py workspace switch <id>' to select a workspace")
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
        print("  Create your first workspace with: python3 run.py workspace create")
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
        print(f"  python3 run.py workspace switch {workspace_id}")
        print()

    except ValueError as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


def cmd_workspace_reset(args):
    """Reset workspace by clearing recent titles and deleting unpublished records"""
    from yt_autopilot.core.workspace_manager import reset_workspace, load_workspace_config
    from yt_autopilot.io.datastore import list_workspace_records

    # Determine which workspaces to reset
    if args.workspace_id:
        workspace_ids = [args.workspace_id]
        # Validate workspace exists
        try:
            load_workspace_config(args.workspace_id)
        except FileNotFoundError:
            print(f"\n❌ Error: Workspace '{args.workspace_id}' not found\n")
            cmd_workspace_list(args)
            sys.exit(1)
    elif args.all:
        workspaces = list_workspaces()
        workspace_ids = [ws['workspace_id'] for ws in workspaces]
        if not workspace_ids:
            print("\n⚠️  No workspaces found\n")
            return
    else:
        # Default: active workspace only
        try:
            workspace = get_active_workspace()
            workspace_ids = [workspace['workspace_id']]
        except RuntimeError:
            print("\n⚠️  No active workspace found\n")
            print("Use --workspace-id <id> to specify a workspace")
            print("Or use --all to reset all workspaces\n")
            sys.exit(1)

    # Analysis phase
    print()
    print("=" * 70)
    print("WORKSPACE RESET ANALYSIS")
    print("=" * 70)
    print()

    workspace_data = []
    total_titles = 0
    total_records = 0
    total_published = 0

    for ws_id in workspace_ids:
        try:
            config = load_workspace_config(ws_id)
            records = list_workspace_records(ws_id, include_all_states=True)

            titles_count = len(config.get('recent_titles', []))
            published_count = sum(1 for r in records if r.get('production_state') == 'SCHEDULED_ON_YOUTUBE')
            unpublished_count = len(records) - published_count

            workspace_data.append({
                'id': ws_id,
                'name': config['workspace_name'],
                'titles': titles_count,
                'unpublished': unpublished_count,
                'published': published_count,
                'records': records
            })

            total_titles += titles_count
            total_records += unpublished_count
            total_published += published_count

        except Exception as e:
            print(f"⚠️  Warning: Could not analyze workspace '{ws_id}': {e}")
            continue

    if not workspace_data:
        print("No workspaces to reset\n")
        return

    # Display analysis
    print(f"Workspaces to reset: {len(workspace_data)}")
    print()

    for ws in workspace_data:
        print(f"• {ws['name']} ({ws['id']})")
        print(f"  - {ws['titles']} recent titles")
        print(f"  - {ws['unpublished']} unpublished records")
        print(f"  - {ws['published']} published records (will be kept)")
        print()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print(f"Will DELETE:")
    print(f"  • {total_titles} recent title entries")
    print(f"  • {total_records} unpublished datastore records")
    print()
    print(f"Will KEEP:")
    print(f"  • {total_published} published video records")
    print(f"  • Workspace configurations")
    print(f"  • Backup will be created")
    print()

    # Dry run mode
    if args.dry_run:
        print("=" * 70)
        print("DRY RUN MODE - No changes made")
        print("=" * 70)
        print()
        print("Remove --dry-run to execute the reset")
        print()
        return

    # Confirmation
    if not args.yes:
        print("=" * 70)
        response = input("Continue with workspace reset? [y/N]: ").strip().lower()
        print()
        if response != 'y':
            print("Reset cancelled\n")
            return

    # Execution phase
    print("=" * 70)
    print("EXECUTING WORKSPACE RESET")
    print("=" * 70)
    print()

    total_deleted_records = 0

    for ws in workspace_data:
        ws_id = ws['id']
        print(f"Processing: {ws['name']} ({ws_id})...")

        try:
            # Reset workspace (clears titles and deletes records)
            result = reset_workspace(ws_id, keep_published=True)

            deleted_records = result['records_deleted']
            total_deleted_records += deleted_records

            print(f"  ✓ Cleared {result['titles_cleared']} recent titles")
            print(f"  ✓ Deleted {deleted_records} unpublished datastore records")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue

        print()

    # Final report
    print("=" * 70)
    print("WORKSPACE RESET COMPLETE")
    print("=" * 70)
    print()
    print(f"✓ Reset {len(workspace_data)} workspace(s)")
    print(f"✓ Deleted {total_deleted_records} unpublished datastore records")
    print(f"✓ Kept {total_published} published records")
    print()
    print(f"Backup: data/records.jsonl.backup_*")
    print()
    print("Next steps:")
    print("  python3 run.py generate")
    print()


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
        brand_tone = workspace.get('brand_tone', 'Not set')
        if len(brand_tone) > 200:
            print(f"Brand tone: {brand_tone[:200]}... [{len(brand_tone)} chars total]")
        else:
            print(f"Brand tone: {brand_tone}")
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
        print(f"Internal Quality Check: {package.status}")
        print(f"Title: {package.video_plan.working_title}")
        print()

        # Extract metadata
        hook = package.script.hook if hasattr(package.script, 'hook') else "N/A"
        num_scenes = len(package.visuals.scenes) if hasattr(package.visuals, 'scenes') else 0
        total_duration = sum(
            scene.est_duration_seconds
            for scene in package.visuals.scenes
            if hasattr(scene, 'est_duration_seconds')
        ) if hasattr(package.visuals, 'scenes') else 0

        # Show hook and metadata
        if hook != "N/A":
            # Truncate long hooks
            hook_display = hook[:150] + "..." if len(hook) > 150 else hook
            print(f"Hook: \"{hook_display}\"")

        print(f"Scenes: {num_scenes} scenes | Duration: ~{total_duration} seconds")
        print()

        # Save script draft if APPROVED
        script_id = None
        if package.status == "APPROVED":
            # Propose publication date 2 days from now
            proposed_datetime = (datetime.utcnow() + timedelta(days=2)).isoformat() + "Z"

            # Save script draft for Gate 1 (human review)
            script_id = save_script_draft(
                ready=package,
                publish_datetime_iso=proposed_datetime,
                workspace_id=workspace['workspace_id']
            )

            print(f"✓ Script saved for human review: SCRIPT_PENDING_REVIEW")
            print(f"Script ID: {script_id}")
            print()

            # Next steps
            print("💡 Next steps:")
            print(f"  - Review full script: python3 run.py review show-script {script_id}")
            print(f"  - Approve for asset generation: python3 run.py review approve-script {script_id} --approved-by \"you@company\"")
            print()
            print("⚠️  Note: Approval will trigger expensive API calls (~$5-10 USD)")
        else:
            # Show rejection reason if rejected
            rejection_reason = getattr(package, 'rejection_reason', 'No reason provided')
            print(f"⚠️  Rejection reason: {rejection_reason}")
            print()
            print("(Script NOT saved in datastore - internal quality check failed)")
            print()

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
            print("Switch workspace with: python3 run.py workspace switch <id>")
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
        print("  python3 run.py generate")
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
            hook_preview = hook[:120] + "..." if len(hook) > 120 else hook
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
    print(f"  1. Review script details: python3 run.py review show-script <script_id>")
    print(f"  2. Approve script: python3 run.py review approve-script <script_id> --approved-by \"you@company\"")
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
            ai_tool_prompt = scene.get('prompt_for_ai_tool', '')
            tool_suggestion = scene.get('tool_suggestion', 'Any AI video tool')
            duration = scene.get('est_duration_seconds', 0)

            print(f"SCENE {scene_id} (~{duration}s)")
            print(f"  Voiceover:")
            print(f"    \"{voiceover}\"")
            print()
            print(f"  Visual Prompt ({tool_suggestion}): [{len(ai_tool_prompt)} chars]")
            # Show full prompt (critical for verifying scene differentiation)
            print(f"    {ai_tool_prompt}")
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
    if len(description) > 500:
        print(f"  {description[:500]}...")
        print(f"  [{len(description)} chars total]")
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
    print("TO APPROVE THIS SCRIPT:")
    print(f"  python3 run.py review approve-script {script_id} --approved-by \"your@email\"")
    print()
    print("Approval will automatically:")
    print("  ✓ Export content package to Markdown with AI-ready prompts")
    print("  ✓ Mark script as READY_FOR_GENERATION")
    print()
    print("OPTIONAL: Generate visual deck with reference images:")
    print(f"  python3 run.py review export-visual-deck {script_id}")
    print("  - Creates DALL-E 3 reference images for each scene")
    print("  - Cost: ~$0.04 per scene")
    print("  - Helps visualize the script like professional presentations")
    print("=" * 70)


def cmd_export_visual_deck(args):
    """Generate visual deck with reference images for script (Phase 1)."""
    from yt_autopilot.core.schemas import ContentPackage, VideoPlan, VideoScript, VisualPlan, VisualScene, PublishingPackage, EditorialDecision
    from yt_autopilot.services import generate_scene_reference_images
    from yt_autopilot.io.exports import export_content_package_to_markdown
    from yt_autopilot.core.workspace_manager import load_workspace_config

    script_id = args.script_id

    print("=" * 70)
    print("GENERATING VISUAL DECK WITH REFERENCE IMAGES")
    print("=" * 70)
    print()
    print(f"Script ID: {script_id}")
    print()

    # Load script draft
    draft = get_script_draft(script_id)
    if draft is None:
        print("ERROR: Script draft not found")
        sys.exit(1)

    workspace_id = draft.get('workspace_id')
    if not workspace_id:
        print("ERROR: Workspace ID not found in draft")
        sys.exit(1)

    # Load workspace config
    try:
        workspace = load_workspace_config(workspace_id)
    except FileNotFoundError:
        print(f"ERROR: Workspace '{workspace_id}' not found")
        sys.exit(1)

    print(f"Workspace: {workspace['workspace_name']} ({workspace_id})")
    print()

    # Reconstruct ContentPackage from draft
    print("⚙️  Reconstructing ContentPackage from draft...")
    try:
        # Reconstruct VisualScenes
        scenes_data = draft.get('visuals', {}).get('scenes', [])
        scenes = [VisualScene(**scene) for scene in scenes_data]

        # Reconstruct ContentPackage
        visuals_data = draft.get('visuals', {})
        content_package = ContentPackage(
            status=draft.get('status', 'APPROVED'),
            video_plan=VideoPlan(**draft.get('video_plan', {})),
            script=VideoScript(**draft.get('script', {})),
            visuals=VisualPlan(
                scenes=scenes,
                style_notes=visuals_data.get('style_notes', ''),
                aspect_ratio=visuals_data.get('aspect_ratio', '9:16'),
                visual_context_id=visuals_data.get('visual_context_id'),
                visual_context_name=visuals_data.get('visual_context_name'),
                character_profile_id=visuals_data.get('character_profile_id'),
                character_description=visuals_data.get('character_description'),
                video_style_mode=visuals_data.get('video_style_mode', 'character_based'),
                ai_selected_format=visuals_data.get('ai_selected_format'),
                format_rationale=visuals_data.get('format_rationale')
            ),
            publishing=PublishingPackage(**draft.get('publishing', {})),
            rejection_reason=draft.get('rejection_reason'),
            llm_raw_script=draft.get('llm_raw_script'),
            final_script_text=draft.get('final_script_text'),
            editorial_decision=EditorialDecision(**draft['editorial_decision']) if draft.get('editorial_decision') else None
        )
    except Exception as e:
        print(f"ERROR: Failed to reconstruct ContentPackage: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("✓ ContentPackage reconstructed")
    print()

    # Generate reference images
    print("🎨 Generating reference images with DALL-E 3...")
    print()
    print("⚠️  WARNING: This will trigger DALL-E 3 API calls:")
    print(f"  - {len(scenes)} images at ~$0.04 each")
    print(f"  - Estimated cost: ~${len(scenes) * 0.04:.2f} USD")
    print()

    response = input("Continue? [y/N]: ").strip().lower()
    if response != 'y':
        print("Cancelled.")
        return

    try:
        content_package = generate_scene_reference_images(
            content_package,
            script_id,
            workspace
        )
        print()
        print("✓ Reference images generated")
        print()
    except Exception as e:
        print(f"ERROR: Failed to generate reference images: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Export visual deck
    print("📄 Exporting visual deck with embedded images...")
    try:
        from pathlib import Path
        from yt_autopilot.core.config import get_config

        config = get_config()
        output_dir = config["OUTPUT_DIR"] / workspace_id / script_id
        markdown_path = output_dir / "visual_deck.md"

        # Export with reference images
        export_content_package_to_markdown(
            content_package,
            script_id,
            workspace,
            output_dir=output_dir
        )

        # Rename to visual_deck.md
        content_package_path = output_dir / "content_package.md"
        if content_package_path.exists():
            content_package_path.rename(markdown_path)

        print()
        print("=" * 70)
        print("✓ SUCCESS: Visual deck generated")
        print("=" * 70)
        print()
        print(f"Visual deck: {markdown_path}")
        print(f"Reference images: {output_dir / 'reference_images'}")
        print()
        print("You can now:")
        print("  1. Open visual_deck.md to see the complete visual breakdown")
        print("  2. Copy AI prompts from the markdown to your video generation tool")
        print("  3. Use reference images as visual guides")
        print("=" * 70)

    except Exception as e:
        print(f"ERROR: Failed to export visual deck: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_review_approve_script(args):
    """Approve script and trigger asset generation (Gate 1 → Gate 2)."""
    script_id = args.script_id
    approved_by = args.approved_by

    if not approved_by:
        print("ERROR: --approved-by is required")
        print("Example: python3 run.py review approve-script <script_id> --approved-by \"dan@company\"")
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

        # Phase 4.1: Automatic Markdown export after approval
        print("=" * 70)
        print("✓ Script approved - generating content package export...")
        print("=" * 70)
        print()

        # Load workspace config
        workspace_id = draft.get('workspace_id')
        output_dir = None  # Initialize to avoid UnboundLocalError

        if workspace_id:
            try:
                from yt_autopilot.core.workspace_manager import load_workspace_config
                from yt_autopilot.io.exports import export_content_package_to_markdown
                from yt_autopilot.core.schemas import ContentPackage, VideoPlan, VideoScript, VisualPlan, VisualScene, PublishingPackage, EditorialDecision
                from pathlib import Path

                workspace = load_workspace_config(workspace_id)

                # Reconstruct ContentPackage from draft
                scenes_data = draft.get('visuals', {}).get('scenes', [])
                scenes = [VisualScene(**scene) for scene in scenes_data]

                visuals_data = draft.get('visuals', {})
                content_package = ContentPackage(
                    status=draft.get('status', 'APPROVED'),
                    video_plan=VideoPlan(**draft.get('video_plan', {})),
                    script=VideoScript(**draft.get('script', {})),
                    visuals=VisualPlan(
                        scenes=scenes,
                        style_notes=visuals_data.get('style_notes', ''),
                        aspect_ratio=visuals_data.get('aspect_ratio', '9:16'),
                        visual_context_id=visuals_data.get('visual_context_id'),
                        visual_context_name=visuals_data.get('visual_context_name'),
                        character_profile_id=visuals_data.get('character_profile_id'),
                        character_description=visuals_data.get('character_description'),
                        video_style_mode=visuals_data.get('video_style_mode', 'character_based'),
                        ai_selected_format=visuals_data.get('ai_selected_format'),
                        format_rationale=visuals_data.get('format_rationale')
                    ),
                    publishing=PublishingPackage(**draft.get('publishing', {})),
                    rejection_reason=draft.get('rejection_reason'),
                    llm_raw_script=draft.get('llm_raw_script'),
                    final_script_text=draft.get('final_script_text'),
                    editorial_decision=EditorialDecision(**draft['editorial_decision']) if draft.get('editorial_decision') else None
                )

                # Export to Markdown
                config = get_config()
                output_dir = config["OUTPUT_DIR"] / workspace_id / script_id
                markdown_path = export_content_package_to_markdown(
                    content_package,
                    script_id,
                    workspace
                )

                print(f"✓ Content package exported: {markdown_path}")
                print()
            except Exception as export_error:
                print(f"⚠️  Warning: Failed to auto-export content package: {export_error}")
                print("   You can manually export later with:")
                print(f"     python3 run.py review export-visual-deck {script_id}")
                print()

        print("=" * 70)
        print("✓ SUCCESS: Script approved for content package")
        print("=" * 70)
        print(f"Script ID: {script_id}")
        print(f"New state: READY_FOR_GENERATION")
        print(f"Approved by: {approved_by}")
        print()
        print("NEXT STEPS:")
        print("  1. Review the exported content package:")
        if output_dir:
            print(f"     {output_dir / 'content_package.md'}")
        else:
            print("     [Export failed - use export-visual-deck command to retry]")
        print()
        print("  2. (Optional) Generate visual reference images:")
        print(f"       python3 run.py review export-visual-deck {script_id}")
        print("       This will add DALL-E 3 reference images (~$0.04 per scene)")
        print()
        print("  3. Copy AI prompts to your preferred AI video tool:")
        print("       - RunwayML Gen-3 Alpha")
        print("       - Luma Dream Machine")
        print("       - Pika Labs")
        print()
        print("  4. Assemble video manually and upload to YouTube")
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
            print("Switch workspace with: python3 run.py workspace switch <id>")
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
    # Print first 500 chars of description
    if len(description) > 500:
        print(f"  {description[:500]}...")
        print(f"  [{len(description)} chars total]")
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
        print(f"  Thumbnail Prompt: {thumbnail_prompt[:300]}{'...' if len(thumbnail_prompt) > 300 else ''}")
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
    print("Next steps - Manual workflow:")
    print("  1. Review all exported assets (audio, video clips, script)")
    print("  2. Assemble final video using your preferred editor")
    print("  3. Upload to YouTube manually")
    print()
    print("  (Automated upload coming in future release)")
    print("=" * 70)

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

    # workspace reset
    ws_reset = workspace_subparsers.add_parser("reset", help="Reset workspace by clearing recent titles and deleting unpublished records")
    ws_reset.add_argument("--workspace-id", help="Workspace ID to reset (default: active workspace)")
    ws_reset.add_argument("--all", action="store_true", help="Reset all workspaces")
    ws_reset.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    ws_reset.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    ws_reset.set_defaults(func=cmd_workspace_reset)

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

    r_approve_script = review_subparsers.add_parser("approve-script", help="[Gate 1] Approve script for content package export")
    r_approve_script.add_argument("script_id", help="Script internal ID")
    r_approve_script.add_argument("--approved-by", required=True, help="Approver identifier (e.g., dan@company)")
    r_approve_script.set_defaults(func=cmd_review_approve_script)

    r_export_deck = review_subparsers.add_parser("export-visual-deck", help="[Gate 1] Generate visual deck with DALL-E 3 reference images")
    r_export_deck.add_argument("script_id", help="Script internal ID")
    r_export_deck.set_defaults(func=cmd_export_visual_deck)

    # Gate 2: Video review (DEPRECATED - will be removed in Phase 2)
    r_stats = review_subparsers.add_parser("stats", help="Show datastore statistics and state distribution")
    r_stats.set_defaults(func=cmd_review_stats)

    r_list = review_subparsers.add_parser("list", help="[Gate 2] List all videos pending review")
    r_list.add_argument("--all-workspaces", action="store_true", help="Show videos from all workspaces (default: current workspace only)")
    r_list.set_defaults(func=cmd_review_list)

    r_show = review_subparsers.add_parser("show", help="[Gate 2] Show details of a specific draft")
    r_show.add_argument("video_id", help="Video internal ID")
    r_show.set_defaults(func=cmd_review_show)

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
            print("Run 'python3 run.py --help' to see available commands")
            print()
        except RuntimeError:
            print()
            print("⚠️  No active workspace found!")
            print()
            cmd_workspace_list(args)
            print()
            print("Run 'python3 run.py workspace switch <id>' to select a workspace")
            print("Or run 'python3 run.py workspace create' to create a new one")
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
