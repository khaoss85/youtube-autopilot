#!/usr/bin/env python3
"""
migrate_legacy_states.py

Migrates legacy production states to new Step 07.3 naming convention.

Legacy → New:
  HUMAN_REVIEW_PENDING → VIDEO_PENDING_REVIEW

This script:
1. Creates automatic backup of records.jsonl
2. Reads all records
3. Updates legacy states to new names
4. Writes back to file
5. Reports what changed

Usage:
  python tools/migrate_legacy_states.py                 # Migrate with confirmation
  python tools/migrate_legacy_states.py --dry-run       # Show what would change
  python tools/migrate_legacy_states.py --yes           # Auto-confirm (no prompt)
"""

import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from yt_autopilot.core.config import get_config


STATE_MIGRATIONS = {
    "HUMAN_REVIEW_PENDING": "VIDEO_PENDING_REVIEW"
}


def get_datastore_path() -> Path:
    """Get path to datastore file."""
    config = get_config()
    data_dir = config["PROJECT_ROOT"] / "data"
    return data_dir / "records.jsonl"


def create_backup(datastore_path: Path) -> Path:
    """Create timestamped backup of datastore."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = datastore_path.parent / f"records.jsonl.backup_{timestamp}"
    shutil.copy2(datastore_path, backup_path)
    return backup_path


def analyze_states(datastore_path: Path) -> dict:
    """Analyze current state distribution."""
    if not datastore_path.exists():
        return {}

    state_counts = {}

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line.strip())
            state = record.get("production_state", "UNKNOWN")
            state_counts[state] = state_counts.get(state, 0) + 1

    return state_counts


def migrate_records(datastore_path: Path, dry_run: bool = False) -> dict:
    """
    Migrate legacy states to new names.

    Returns:
        dict with keys: 'migrated', 'unchanged', 'changes'
    """
    if not datastore_path.exists():
        return {"migrated": 0, "unchanged": 0, "changes": []}

    migrated = 0
    unchanged = 0
    changes = []
    updated_records = []

    with open(datastore_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line.strip())
            old_state = record.get("production_state")

            # Check if state needs migration
            if old_state in STATE_MIGRATIONS:
                new_state = STATE_MIGRATIONS[old_state]
                record["production_state"] = new_state

                # Track change
                changes.append({
                    "record_id": record.get("video_internal_id") or record.get("script_internal_id"),
                    "old_state": old_state,
                    "new_state": new_state,
                    "title": record.get("title", "N/A")
                })

                migrated += 1
            else:
                unchanged += 1

            updated_records.append(record)

    # Write back (if not dry run)
    if not dry_run:
        with open(datastore_path, "w", encoding="utf-8") as f:
            for record in updated_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "migrated": migrated,
        "unchanged": unchanged,
        "changes": changes
    }


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy production states to Step 07.3 naming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration (safe)
  python tools/migrate_legacy_states.py --dry-run

  # Run migration with confirmation prompt
  python tools/migrate_legacy_states.py

  # Run migration without confirmation
  python tools/migrate_legacy_states.py --yes
"""
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying files"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Auto-confirm migration (skip prompt)"
    )

    args = parser.parse_args()

    datastore_path = get_datastore_path()

    print("=" * 70)
    print("LEGACY STATE MIGRATION")
    print("=" * 70)
    print()

    if not datastore_path.exists():
        print("ERROR: Datastore file not found")
        print(f"  Expected: {datastore_path}")
        print()
        sys.exit(1)

    print(f"Datastore: {datastore_path}")
    print()

    # Analyze current states
    print("CURRENT STATE DISTRIBUTION:")
    print("-" * 70)
    state_counts = analyze_states(datastore_path)

    for state, count in sorted(state_counts.items()):
        marker = " → WILL MIGRATE" if state in STATE_MIGRATIONS else ""
        print(f"  {state}: {count}{marker}")

    print()

    # Count migrations
    migration_count = sum(
        count for state, count in state_counts.items()
        if state in STATE_MIGRATIONS
    )

    if migration_count == 0:
        print("✓ No legacy states found - nothing to migrate")
        print()
        sys.exit(0)

    print(f"MIGRATION PLAN:")
    print("-" * 70)
    for old_state, new_state in STATE_MIGRATIONS.items():
        count = state_counts.get(old_state, 0)
        if count > 0:
            print(f"  {old_state} → {new_state} ({count} records)")

    print()

    if args.dry_run:
        print("DRY RUN MODE: No changes will be made")
        print()

    # Run migration
    result = migrate_records(datastore_path, dry_run=args.dry_run)

    # Show what changed
    if result["changes"]:
        print("CHANGES:")
        print("-" * 70)
        for change in result["changes"]:
            print(f"  [{change['old_state']} → {change['new_state']}]")
            print(f"    ID: {change['record_id']}")
            print(f"    Title: {change['title']}")
            print()

    # Summary
    print("=" * 70)
    if args.dry_run:
        print("DRY RUN SUMMARY")
    else:
        print("MIGRATION SUMMARY")
    print("=" * 70)
    print(f"  Records migrated: {result['migrated']}")
    print(f"  Records unchanged: {result['unchanged']}")
    print()

    if not args.dry_run:
        # Create backup
        backup_path = create_backup(datastore_path)
        print(f"✓ Backup created: {backup_path.name}")
        print(f"✓ Migration complete!")
        print()

        # Show new state distribution
        print("NEW STATE DISTRIBUTION:")
        print("-" * 70)
        new_state_counts = analyze_states(datastore_path)
        for state, count in sorted(new_state_counts.items()):
            print(f"  {state}: {count}")
        print()
    else:
        print("To apply these changes, run without --dry-run:")
        print("  python tools/migrate_legacy_states.py")
        print()


if __name__ == "__main__":
    main()
