#!/usr/bin/env python3
"""
cleanup_datastore.py

Utility to clean up and manage the datastore (data/records.jsonl).

Features:
- List all records grouped by state
- Delete records by state
- Delete records older than N days
- Archive deleted records instead of removing them
- Dry-run mode for safe previewing

Usage:
  # Show statistics
  python tools/cleanup_datastore.py --list-all

  # Preview deletion (safe)
  python tools/cleanup_datastore.py --delete-state HUMAN_REVIEW_PENDING --dry-run

  # Delete all videos pending review
  python tools/cleanup_datastore.py --delete-state VIDEO_PENDING_REVIEW --yes

  # Archive old records instead of deleting
  python tools/cleanup_datastore.py --delete-older-than 30 --archive --yes

  # Delete scripts ready for generation
  python tools/cleanup_datastore.py --delete-state READY_FOR_GENERATION --yes
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from yt_autopilot.core.config import get_config


def get_datastore_path() -> Path:
    """Get path to datastore file."""
    config = get_config()
    data_dir = config["PROJECT_ROOT"] / "data"
    return data_dir / "records.jsonl"


def parse_datetime(dt_str: str) -> datetime:
    """Parse ISO datetime string."""
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        # Try without timezone
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None


def list_all_records(datastore_path: Path) -> dict:
    """
    List all records grouped by state.

    Returns:
        dict: {state: [list of records]}
    """
    if not datastore_path.exists():
        return {}

    records_by_state = {}

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line.strip())
            state = record.get("production_state", "UNKNOWN")

            if state not in records_by_state:
                records_by_state[state] = []

            records_by_state[state].append(record)

    return records_by_state


def filter_records(
    records: list,
    delete_state: str = None,
    delete_older_than_days: int = None
) -> tuple:
    """
    Filter records into keep and delete lists.

    Returns:
        (keep_records, delete_records)
    """
    keep = []
    delete = []

    for record in records:
        should_delete = False

        # Filter by state
        if delete_state and record.get("production_state") == delete_state:
            should_delete = True

        # Filter by age
        if delete_older_than_days:
            saved_at = parse_datetime(record.get("saved_at", ""))
            if saved_at:
                age = datetime.now() - saved_at.replace(tzinfo=None)
                if age.days > delete_older_than_days:
                    should_delete = True

        if should_delete:
            delete.append(record)
        else:
            keep.append(record)

    return keep, delete


def archive_records(datastore_path: Path, records: list) -> Path:
    """Archive deleted records to timestamped file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = datastore_path.parent / f"records.jsonl.archive_{timestamp}"

    with open(archive_path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return archive_path


def cleanup(
    datastore_path: Path,
    delete_state: str = None,
    delete_older_than_days: int = None,
    archive: bool = False,
    dry_run: bool = False
) -> dict:
    """
    Cleanup datastore based on filters.

    Returns:
        dict with keys: 'deleted', 'kept', 'archive_path'
    """
    if not datastore_path.exists():
        return {"deleted": 0, "kept": 0, "archive_path": None}

    # Read all records
    all_records = []
    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            all_records.append(json.loads(line.strip()))

    # Filter
    keep_records, delete_records = filter_records(
        all_records,
        delete_state=delete_state,
        delete_older_than_days=delete_older_than_days
    )

    result = {
        "deleted": len(delete_records),
        "kept": len(keep_records),
        "archive_path": None,
        "deleted_records": delete_records
    }

    # Execute changes (if not dry run)
    if not dry_run:
        # Archive deleted records
        if archive and delete_records:
            archive_path = archive_records(datastore_path, delete_records)
            result["archive_path"] = archive_path

        # Write back kept records
        with open(datastore_path, "w", encoding="utf-8") as f:
            for record in keep_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup and manage datastore records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all records grouped by state
  python tools/cleanup_datastore.py --list-all

  # Preview deletion
  python tools/cleanup_datastore.py --delete-state VIDEO_PENDING_REVIEW --dry-run

  # Delete all HUMAN_REVIEW_PENDING records
  python tools/cleanup_datastore.py --delete-state HUMAN_REVIEW_PENDING --yes

  # Delete records older than 30 days and archive them
  python tools/cleanup_datastore.py --delete-older-than 30 --archive --yes

  # Delete READY_FOR_GENERATION scripts
  python tools/cleanup_datastore.py --delete-state READY_FOR_GENERATION --yes
"""
    )

    parser.add_argument(
        "--list-all",
        action="store_true",
        help="List all records grouped by state (no deletion)"
    )

    parser.add_argument(
        "--delete-state",
        type=str,
        help="Delete all records in this state"
    )

    parser.add_argument(
        "--delete-older-than",
        type=int,
        metavar="DAYS",
        help="Delete records older than N days"
    )

    parser.add_argument(
        "--archive",
        action="store_true",
        help="Archive deleted records to timestamped file"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying files"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm deletion (skip prompt)"
    )

    args = parser.parse_args()

    datastore_path = get_datastore_path()

    print("=" * 70)
    print("DATASTORE CLEANUP UTILITY")
    print("=" * 70)
    print()

    if not datastore_path.exists():
        print("ERROR: Datastore file not found")
        print(f"  Expected: {datastore_path}")
        print()
        sys.exit(1)

    print(f"Datastore: {datastore_path}")
    print()

    # List all mode
    if args.list_all:
        print("RECORDS BY STATE:")
        print("-" * 70)

        records_by_state = list_all_records(datastore_path)

        for state in sorted(records_by_state.keys()):
            records = records_by_state[state]
            print(f"\n{state} ({len(records)} records):")
            print("-" * 70)

            for i, record in enumerate(records, 1):
                record_id = (
                    record.get("video_internal_id") or
                    record.get("script_internal_id") or
                    "N/A"
                )
                title = record.get("title", "N/A")
                saved_at = record.get("saved_at", "N/A")

                print(f"  [{i}] {record_id[:20]}...")
                print(f"      Title: {title[:60]}{'...' if len(title) > 60 else ''}")
                print(f"      Saved: {saved_at}")

        print()
        print("=" * 70)
        print("SUMMARY:")
        print(f"  Total states: {len(records_by_state)}")

        for state, records in records_by_state.items():
            print(f"  {state}: {len(records)}")

        print()
        return

    # Cleanup mode
    if not args.delete_state and not args.delete_older_than:
        print("ERROR: Must specify --delete-state or --delete-older-than")
        print("       or use --list-all to view records")
        print()
        parser.print_help()
        sys.exit(1)

    # Show filters
    print("CLEANUP FILTERS:")
    print("-" * 70)
    if args.delete_state:
        print(f"  Delete state: {args.delete_state}")
    if args.delete_older_than:
        print(f"  Delete older than: {args.delete_older_than} days")
    if args.archive:
        print(f"  Archive mode: YES")
    if args.dry_run:
        print(f"  Dry run mode: YES (no changes)")
    print()

    # Run cleanup
    result = cleanup(
        datastore_path,
        delete_state=args.delete_state,
        delete_older_than_days=args.delete_older_than,
        archive=args.archive,
        dry_run=args.dry_run
    )

    # Show what will be deleted
    if result["deleted"] > 0:
        print("RECORDS TO DELETE:")
        print("-" * 70)

        for i, record in enumerate(result["deleted_records"][:10], 1):
            record_id = (
                record.get("video_internal_id") or
                record.get("script_internal_id") or
                "N/A"
            )
            state = record.get("production_state", "UNKNOWN")
            title = record.get("title", "N/A")
            saved_at = record.get("saved_at", "N/A")

            print(f"  [{i}] {state}")
            print(f"      ID: {record_id}")
            print(f"      Title: {title[:60]}{'...' if len(title) > 60 else ''}")
            print(f"      Saved: {saved_at}")
            print()

        if len(result["deleted_records"]) > 10:
            remaining = len(result["deleted_records"]) - 10
            print(f"  ... and {remaining} more records")
            print()

    # Summary
    print("=" * 70)
    if args.dry_run:
        print("DRY RUN SUMMARY")
    else:
        print("CLEANUP SUMMARY")
    print("=" * 70)
    print(f"  Records to delete: {result['deleted']}")
    print(f"  Records to keep: {result['kept']}")
    print()

    # Confirmation
    if not args.dry_run and not args.yes and result["deleted"] > 0:
        print("⚠️  WARNING: This will permanently modify the datastore!")
        if args.archive:
            print("   (Deleted records will be archived)")
        else:
            print("   (Deleted records will NOT be archived)")
        print()

        response = input("Continue? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            print()
            sys.exit(0)

        print()

        # Re-run without dry run
        result = cleanup(
            datastore_path,
            delete_state=args.delete_state,
            delete_older_than_days=args.delete_older_than,
            archive=args.archive,
            dry_run=False
        )

    if not args.dry_run and result["deleted"] > 0:
        if result["archive_path"]:
            print(f"✓ Archived to: {result['archive_path'].name}")
        print(f"✓ Deleted {result['deleted']} records")
        print(f"✓ Kept {result['kept']} records")
        print()
    elif args.dry_run:
        print("To apply these changes, run without --dry-run:")
        cmd = f"python tools/cleanup_datastore.py"
        if args.delete_state:
            cmd += f" --delete-state {args.delete_state}"
        if args.delete_older_than:
            cmd += f" --delete-older-than {args.delete_older_than}"
        if args.archive:
            cmd += " --archive"
        cmd += " --yes"
        print(f"  {cmd}")
        print()
    elif result["deleted"] == 0:
        print("No records matched the filters.")
        print()


if __name__ == "__main__":
    main()
