#!/usr/bin/env python3
"""
review_console.py

Mini console da riga di comando per gestire la review umana dei video generati.

Comandi:
  list                                  - Elenca tutti i draft in attesa di review
  show <video_internal_id>              - Mostra dettagli di un draft specifico
  publish <video_internal_id> --approved-by "yourname@company"
                                        - Approva e pubblica un draft su YouTube

Questo script è pensato per uso manuale.
NON va schedulato, NON va chiamato automaticamente.
È il gate umano finale prima della pubblicazione.

Example usage:
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

from yt_autopilot.io.datastore import list_pending_review, get_draft_package
from yt_autopilot.pipeline.produce_render_publish import publish_after_approval


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
        description="Human review console for yt_autopilot video drafts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all pending drafts
  python tools/review_console.py list

  # Show details of a specific draft
  python tools/review_console.py show 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d

  # Approve and publish a draft
  python tools/review_console.py publish 6a1b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d --approved-by "dan@company"
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    parser_list = subparsers.add_parser("list", help="List all videos pending review")
    parser_list.set_defaults(func=cmd_list)

    # Show command
    parser_show = subparsers.add_parser("show", help="Show details of a specific draft")
    parser_show.add_argument("video_internal_id", help="UUID of the draft video")
    parser_show.set_defaults(func=cmd_show)

    # Publish command
    parser_publish = subparsers.add_parser("publish", help="Approve and publish a draft to YouTube")
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
