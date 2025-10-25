#!/usr/bin/env python3
"""
review_console.py

Mini console da riga di comando per gestire la review umana dei video generati.

Step 07.3: 2-Gate Workflow
  GATE 1 (Script Review - cheap):
    scripts                             - Elenca script in attesa di review
    show-script <script_id>             - Mostra dettagli script (Concept + Breakdown)
    approve-script <script_id> --approved-by "name"
                                        - Approva script e abilita generazione asset

  GATE 2 (Video Review - expensive):
    list                                - Elenca video in attesa di review
    show <video_id>                     - Mostra dettagli video completo
    publish <video_id> --approved-by "name"
                                        - Approva e pubblica video su YouTube

Questo script è pensato per uso manuale.
NON va schedulato, NON va chiamato automaticamente.
È il gate umano prima della pubblicazione.

Example usage (Step 07.3 workflow):
  # GATE 1: Script review (happens first, cheap)
  python tools/review_console.py scripts
  python tools/review_console.py show-script abc123-script-id
  python tools/review_console.py approve-script abc123-script-id --approved-by "dan@company"

  # GATE 2: Video review (happens after generation, expensive)
  python tools/review_console.py list
  python tools/review_console.py show 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d
  python tools/review_console.py publish 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d --approved-by "dan@company"
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from yt_autopilot.io.datastore import (
    list_pending_review,
    get_draft_package,
    list_pending_script_review,  # Step 07.3 - Gate 1
    get_script_draft,            # Step 07.3 - Gate 1
    approve_script_for_generation  # Step 07.3 - Gate 1
)
from yt_autopilot.pipeline.produce_render_publish import publish_after_approval


# ============================================================================
# GATE 1: SCRIPT REVIEW COMMANDS (Step 07.3)
# ============================================================================

def cmd_scripts(args):
    """List all scripts pending human review (Gate 1)."""
    print("=" * 70)
    print("SCRIPT REVIEW QUEUE (GATE 1 - cheap)")
    print("=" * 70)
    print()

    pending = list_pending_script_review()

    if not pending:
        print("No scripts pending review.")
        print()
        print("TIP: Generate a new script draft with:")
        print("  from yt_autopilot.pipeline.produce_render_publish import generate_script_draft")
        print("  generate_script_draft(publish_datetime_iso='2025-01-15T10:00:00Z')")
        print()
        return

    print(f"Found {len(pending)} script(s) pending review:")
    print()

    for i, script in enumerate(pending, 1):
        print(f"[{i}] {script['production_state']}")
        print(f"  script_internal_id: {script['script_internal_id']}")

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
    print(f"  1. Review script details: python tools/review_console.py show-script <script_id>")
    print(f"  2. Approve script: python tools/review_console.py approve-script <script_id> --approved-by \"you@company\"")
    print("=" * 70)


def cmd_show_script(args):
    """Show detailed script information in 2-level format (Gate 1)."""
    script_id = args.script_internal_id

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
    print(f"  python tools/review_console.py approve-script {script_id} --approved-by \"your@email\"")
    print()
    print("WARNING: Approval will trigger expensive API calls:")
    print("  - Sora 2 video generation (~$$$)")
    print("  - OpenAI TTS audio generation (~$$)")
    print("  - DALL-E 3 thumbnail generation (~$)")
    print("  Total estimated cost: ~$5-10 USD per video")
    print("=" * 70)


def cmd_approve_script(args):
    """Approve script and trigger asset generation (Gate 1 → Gate 2)."""
    script_id = args.script_internal_id
    approved_by = args.approved_by

    if not approved_by:
        print("ERROR: --approved-by is required")
        print("Example: python tools/review_console.py approve-script <script_id> --approved-by \"dan@company\"")
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
        print("       python tools/review_console.py list")
        print("       python tools/review_console.py show <video_id>")
        print()
        print("  3. If satisfied, publish to YouTube:")
        print("       python tools/review_console.py publish <video_id> --approved-by \"your@email\"")
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
# GATE 2: VIDEO REVIEW COMMANDS (existing)
# ============================================================================

def cmd_list(args):
    """List all videos pending human review."""
    print("=" * 70)
    print("PENDING REVIEW QUEUE")
    print("=" * 70)
    print()

    pending = list_pending_review()

    if not pending:
        print("No videos pending review.")
        print()
        return

    print(f"Found {len(pending)} video(s) pending review:")
    print()

    for i, video in enumerate(pending, 1):
        print(f"[{i}] {video['production_state']}")
        print(f"  video_internal_id: {video['video_internal_id']}")
        print(f"  final_video_path: {video['final_video_path']}")
        print(f"  thumbnail_path: {video['thumbnail_path']}")
        print(f"  proposed_title: {video['proposed_title']}")
        print(f"  suggested_publishAt: {video['suggested_publishAt']}")
        print(f"  saved_at: {video['saved_at']}")
        print()


def cmd_show(args):
    """Show detailed information about a specific draft."""
    video_id = args.video_internal_id

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
    print(f"  python tools/review_console.py publish {video_id} --approved-by \"your@email\"")
    print("=" * 70)


def cmd_publish(args):
    """Publish an approved draft to YouTube."""
    video_id = args.video_internal_id
    approved_by = args.approved_by

    if not approved_by:
        print("ERROR: --approved-by is required")
        print("Example: python tools/review_console.py publish <video_id> --approved-by \"dan@company\"")
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


def main():
    parser = argparse.ArgumentParser(
        description="Human review console for yt_autopilot video drafts (Step 07.3: 2-Gate Workflow)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (Step 07.3 - 2-Gate Workflow):

  GATE 1: Script Review (cheap, happens first)
  --------------------------------------------
  # List scripts pending review
  python tools/review_console.py scripts

  # Show script details (Concept Summary + Breakdown)
  python tools/review_console.py show-script abc123-script-id

  # Approve script (enables asset generation)
  python tools/review_console.py approve-script abc123-script-id --approved-by "dan@company"


  GATE 2: Video Review (expensive, happens after generation)
  -----------------------------------------------------------
  # List videos pending review
  python tools/review_console.py list

  # Show video details
  python tools/review_console.py show 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d

  # Approve and publish video
  python tools/review_console.py publish 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d --approved-by "dan@company"
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ========================================================================
    # GATE 1: SCRIPT REVIEW COMMANDS
    # ========================================================================

    # Scripts command
    parser_scripts = subparsers.add_parser("scripts", help="[Gate 1] List all scripts pending review")
    parser_scripts.set_defaults(func=cmd_scripts)

    # Show-script command
    parser_show_script = subparsers.add_parser("show-script", help="[Gate 1] Show script details in 2-level format")
    parser_show_script.add_argument("script_internal_id", help="UUID of the script draft")
    parser_show_script.set_defaults(func=cmd_show_script)

    # Approve-script command
    parser_approve_script = subparsers.add_parser("approve-script", help="[Gate 1] Approve script for asset generation")
    parser_approve_script.add_argument("script_internal_id", help="UUID of the script draft")
    parser_approve_script.add_argument("--approved-by", required=True, help="Approver identifier (e.g., dan@company)")
    parser_approve_script.set_defaults(func=cmd_approve_script)

    # ========================================================================
    # GATE 2: VIDEO REVIEW COMMANDS
    # ========================================================================

    # List command
    parser_list = subparsers.add_parser("list", help="[Gate 2] List all videos pending review")
    parser_list.set_defaults(func=cmd_list)

    # Show command
    parser_show = subparsers.add_parser("show", help="[Gate 2] Show details of a specific draft")
    parser_show.add_argument("video_internal_id", help="UUID of the draft video")
    parser_show.set_defaults(func=cmd_show)

    # Publish command
    parser_publish = subparsers.add_parser("publish", help="[Gate 2] Approve and publish a draft to YouTube")
    parser_publish.add_argument("video_internal_id", help="UUID of the draft video")
    parser_publish.add_argument("--approved-by", required=True, help="Approver identifier (e.g., dan@company)")
    parser_publish.set_defaults(func=cmd_publish)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
