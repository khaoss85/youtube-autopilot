#!/usr/bin/env python3
"""
PR Outreach CLI - Command-line interface for media PR outreach.

Usage:
    python outreach.py campaign list              # List campaigns
    python outreach.py campaign info <id>         # Show campaign info
    python outreach.py campaign create            # Create new campaign

    python outreach.py generate [--campaign <id>] # Generate outreach packages
    python outreach.py generate --dry-run         # Preview without saving

    python outreach.py review emails              # List pending emails
    python outreach.py review show <id>           # Show email details
    python outreach.py approve <id>               # Approve email for sending
    python outreach.py reject <id> --reason "..." # Reject email

    python outreach.py send <id>                  # Send approved email
    python outreach.py send-all                   # Send all approved emails

    python outreach.py stats [--campaign <id>]    # Show campaign statistics
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from pr_outreach.core.schemas import (
    CampaignConfig,
    ProductInfo,
    SenderPersona,
    OutreachStatus,
    ValidationGate
)
from pr_outreach.pipeline.build_outreach_package import build_outreach_package
from pr_outreach.io.outreach_datastore import (
    get_pending_emails,
    get_outreach_by_id,
    approve_email,
    reject_email,
    mark_as_sent,
    get_campaign_stats,
    get_all_outreach
)
from pr_outreach.services.email_sender import send_email


CAMPAIGNS_DIR = "campaigns"


def main():
    parser = argparse.ArgumentParser(
        description="PR Outreach CLI - Automated media PR outreach",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Campaign commands
    campaign_parser = subparsers.add_parser("campaign", help="Campaign management")
    campaign_sub = campaign_parser.add_subparsers(dest="campaign_action")

    campaign_sub.add_parser("list", help="List all campaigns")
    campaign_info = campaign_sub.add_parser("info", help="Show campaign info")
    campaign_info.add_argument("campaign_id", help="Campaign ID")
    campaign_sub.add_parser("create", help="Create new campaign (interactive)")

    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate outreach packages")
    generate_parser.add_argument("--campaign", "-c", help="Campaign ID")
    generate_parser.add_argument("--max", "-m", type=int, default=1, help="Max packages to generate")
    generate_parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    generate_parser.add_argument("--no-llm", action="store_true", help="Disable LLM (use heuristics)")

    # Review commands
    review_parser = subparsers.add_parser("review", help="Review outreach packages")
    review_sub = review_parser.add_subparsers(dest="review_action")

    review_sub.add_parser("emails", help="List pending emails")
    review_show = review_sub.add_parser("show", help="Show email details")
    review_show.add_argument("outreach_id", help="Outreach ID")

    # Approve command
    approve_parser = subparsers.add_parser("approve", help="Approve email for sending")
    approve_parser.add_argument("outreach_id", help="Outreach ID")
    approve_parser.add_argument("--approved-by", required=True, help="Approver email/name")

    # Reject command
    reject_parser = subparsers.add_parser("reject", help="Reject email")
    reject_parser.add_argument("outreach_id", help="Outreach ID")
    reject_parser.add_argument("--reason", required=True, help="Rejection reason")

    # Send commands
    send_parser = subparsers.add_parser("send", help="Send approved email")
    send_parser.add_argument("outreach_id", help="Outreach ID")

    subparsers.add_parser("send-all", help="Send all approved emails")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show campaign statistics")
    stats_parser.add_argument("--campaign", "-c", help="Campaign ID (optional)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to command handlers
    if args.command == "campaign":
        cmd_campaign(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "review":
        cmd_review(args)
    elif args.command == "approve":
        cmd_approve(args)
    elif args.command == "reject":
        cmd_reject(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "send-all":
        cmd_send_all(args)
    elif args.command == "stats":
        cmd_stats(args)


def cmd_campaign(args):
    """Handle campaign commands."""
    if args.campaign_action == "list":
        campaigns = list_campaigns()
        if not campaigns:
            print("No campaigns found.")
            print(f"Create one in {CAMPAIGNS_DIR}/ or use 'outreach.py campaign create'")
            return

        print("\nAvailable Campaigns:")
        print("-" * 60)
        for c in campaigns:
            print(f"  {c['campaign_id']}: {c['campaign_name']}")
            print(f"    Product: {c['product_name']}")
            print(f"    Niche: {c['niche_id']}")
            print()

    elif args.campaign_action == "info":
        config = load_campaign(args.campaign_id)
        if not config:
            print(f"Campaign not found: {args.campaign_id}")
            return

        print(f"\nCampaign: {config.campaign_name}")
        print("=" * 60)
        print(f"ID: {config.campaign_id}")
        print(f"Niche: {config.niche_id}")
        print(f"Language: {config.target_language}")
        print()
        print("Product:")
        print(f"  Name: {config.product.name}")
        print(f"  Tagline: {config.product.tagline}")
        print(f"  Website: {config.product.website_url}")
        print()
        print("Sender:")
        print(f"  Name: {config.sender_persona.name}")
        print(f"  Email: {config.sender_persona.email}")
        print(f"  Title: {config.sender_persona.title}")
        print()
        print("Search Queries:")
        for q in config.search_queries:
            print(f"  - {q}")

    elif args.campaign_action == "create":
        create_campaign_interactive()


def cmd_generate(args):
    """Generate outreach packages."""
    # Load campaign
    campaign_id = args.campaign or get_active_campaign()
    if not campaign_id:
        print("No campaign specified. Use --campaign or set active campaign.")
        return

    config = load_campaign(campaign_id)
    if not config:
        print(f"Campaign not found: {campaign_id}")
        return

    print(f"\nGenerating outreach for: {config.campaign_name}")
    print(f"Product: {config.product.name}")
    print(f"Max packages: {args.max}")
    if args.dry_run:
        print("[DRY RUN MODE]")
    print()

    packages = build_outreach_package(
        campaign_config=config,
        max_articles_to_process=args.max,
        use_llm=not args.no_llm,
        dry_run=args.dry_run
    )

    print(f"\nGenerated {len(packages)} package(s)")

    if packages:
        print("\nPackages:")
        for pkg in packages:
            print(f"  - {pkg.outreach_id[:8]}...")
            print(f"    Article: {pkg.article.title[:50]}...")
            print(f"    Author: {pkg.author.name}")
            print(f"    Quality: {pkg.overall_quality_score:.2f}")
            print()

        if not args.dry_run:
            print("Use 'outreach.py review emails' to review and approve")


def cmd_review(args):
    """Handle review commands."""
    if args.review_action == "emails":
        pending = get_pending_emails()

        if not pending:
            print("No emails pending review.")
            return

        print(f"\nPending Emails ({len(pending)}):")
        print("-" * 70)

        for p in pending:
            print(f"ID: {p['outreach_id'][:12]}...")
            print(f"  Article: {p['article_title'][:50]}...")
            print(f"  Author: {p['author_name']} <{p.get('author_email', 'no email')}>")
            print(f"  Subject: {p['email_subject']}")
            print(f"  Quality: {p['overall_quality_score']:.2f}")
            print(f"  Created: {p['created_at']}")
            print()

    elif args.review_action == "show":
        record = get_outreach_by_id(args.outreach_id)

        if not record:
            print(f"Outreach not found: {args.outreach_id}")
            return

        print("\n" + "=" * 70)
        print("OUTREACH DETAILS")
        print("=" * 70)

        print(f"\nID: {record['outreach_id']}")
        print(f"Status: {record['status']}")
        print(f"Campaign: {record['campaign_id']}")
        print(f"Created: {record['created_at']}")

        print("\n--- ARTICLE ---")
        print(f"Title: {record['article_title']}")
        print(f"URL: {record['article_url']}")
        print(f"Domain: {record['article_domain']} (DA: {record['article_domain_authority']})")

        print("\n--- AUTHOR ---")
        print(f"Name: {record['author_name']}")
        print(f"Email: {record.get('author_email', 'N/A')}")
        if record.get('author_email_verified'):
            print("  (verified)")
        if record.get('author_linkedin'):
            print(f"LinkedIn: {record['author_linkedin']}")
        if record.get('author_twitter'):
            print(f"Twitter: @{record['author_twitter']}")

        print("\n--- EMAIL ---")
        print(f"Subject: {record['email_subject']}")
        print()
        print(record['email_body'])

        print("\n--- QUALITY SCORES ---")
        print(f"Spam Score: {record['spam_score']:.2f} (lower is better)")
        print(f"Personalization: {record['personalization_score']:.2f}")
        print(f"Overall Quality: {record['overall_quality_score']:.2f}")

        print("\n--- AI REASONING ---")
        print(f"Article Selection: {record.get('article_selection_reasoning', 'N/A')}")
        print(f"Positioning: {record.get('positioning_reasoning', 'N/A')[:100]}...")
        print(f"Strategy: {record.get('strategy_reasoning', 'N/A')}")

        print("\n" + "=" * 70)
        print("To approve: outreach.py approve", args.outreach_id, "--approved-by YOUR_EMAIL")
        print("To reject:  outreach.py reject", args.outreach_id, "--reason 'reason'")


def cmd_approve(args):
    """Approve an email."""
    success = approve_email(args.outreach_id, args.approved_by)

    if success:
        print(f"✓ Email approved: {args.outreach_id}")
        print(f"  Approved by: {args.approved_by}")
        print("\nTo send: outreach.py send", args.outreach_id)
    else:
        print(f"✗ Failed to approve: {args.outreach_id}")


def cmd_reject(args):
    """Reject an email."""
    success = reject_email(args.outreach_id, args.reason)

    if success:
        print(f"✓ Email rejected: {args.outreach_id}")
        print(f"  Reason: {args.reason}")
    else:
        print(f"✗ Failed to reject: {args.outreach_id}")


def cmd_send(args):
    """Send an approved email."""
    record = get_outreach_by_id(args.outreach_id)

    if not record:
        print(f"Outreach not found: {args.outreach_id}")
        return

    if record['status'] != OutreachStatus.APPROVED.value:
        print(f"Email not approved. Status: {record['status']}")
        return

    to_email = record.get('author_email')
    if not to_email:
        print("No email address for author")
        return

    print(f"Sending to: {to_email}")
    print(f"Subject: {record['email_subject']}")

    # Confirm
    confirm = input("\nSend this email? (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return

    # Send
    success, result, provider = send_email(
        to_email=to_email,
        subject=record['email_subject'],
        body=record['email_body']
    )

    if success:
        mark_as_sent(args.outreach_id, result)
        print(f"✓ Email sent via {provider}")
        print(f"  Message ID: {result}")
    else:
        print(f"✗ Failed to send: {result}")


def cmd_send_all(args):
    """Send all approved emails."""
    approved = get_all_outreach(status=OutreachStatus.APPROVED)

    if not approved:
        print("No approved emails to send.")
        return

    print(f"Found {len(approved)} approved email(s)")

    confirm = input(f"Send all {len(approved)} emails? (y/N): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return

    sent = 0
    failed = 0

    for record in approved:
        to_email = record.get('author_email')
        if not to_email:
            print(f"Skipping {record['outreach_id']}: no email")
            continue

        success, result, provider = send_email(
            to_email=to_email,
            subject=record['email_subject'],
            body=record['email_body']
        )

        if success:
            mark_as_sent(record['outreach_id'], result)
            print(f"✓ Sent to {to_email}")
            sent += 1
        else:
            print(f"✗ Failed: {to_email} - {result}")
            failed += 1

    print(f"\nSent: {sent}, Failed: {failed}")


def cmd_stats(args):
    """Show campaign statistics."""
    campaign_id = args.campaign

    if campaign_id:
        campaigns = [(campaign_id, load_campaign(campaign_id))]
    else:
        campaigns = [(c['campaign_id'], load_campaign(c['campaign_id'])) for c in list_campaigns()]

    for cid, config in campaigns:
        if not config:
            continue

        stats = get_campaign_stats(cid)

        print(f"\n{config.campaign_name} ({cid})")
        print("=" * 50)
        print(f"Generated: {stats.total_emails_generated}")
        print(f"Sent: {stats.total_emails_sent}")
        print(f"Opens: {stats.total_opens} ({stats.open_rate:.1%})")
        print(f"Replies: {stats.total_replies} ({stats.reply_rate:.1%})")
        print(f"  - Positive: {stats.positive_replies}")
        print(f"  - Neutral: {stats.neutral_replies}")
        print(f"  - Negative: {stats.negative_replies}")
        print()
        print("Quality Averages:")
        print(f"  Spam Score: {stats.avg_spam_score:.2f}")
        print(f"  Personalization: {stats.avg_personalization_score:.2f}")
        print(f"  Overall: {stats.avg_quality_score:.2f}")


def list_campaigns() -> list:
    """List all available campaigns."""
    campaigns = []

    if not os.path.exists(CAMPAIGNS_DIR):
        return campaigns

    for filename in os.listdir(CAMPAIGNS_DIR):
        if filename.endswith('.json'):
            path = os.path.join(CAMPAIGNS_DIR, filename)
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    campaigns.append({
                        'campaign_id': data.get('campaign_id', filename[:-5]),
                        'campaign_name': data.get('campaign_name', 'Unknown'),
                        'product_name': data.get('product', {}).get('name', 'Unknown'),
                        'niche_id': data.get('niche_id', 'Unknown')
                    })
            except (json.JSONDecodeError, IOError):
                continue

    return campaigns


def load_campaign(campaign_id: str) -> CampaignConfig:
    """Load a campaign configuration."""
    path = os.path.join(CAMPAIGNS_DIR, f"{campaign_id}.json")

    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        # Parse nested objects
        product = ProductInfo(**data['product'])
        sender = SenderPersona(**data['sender_persona'])

        # Parse validation gates
        gates = {}
        for gate_name, gate_data in data.get('validation_gates', {}).items():
            gates[gate_name] = ValidationGate(**gate_data)

        return CampaignConfig(
            campaign_id=data['campaign_id'],
            campaign_name=data['campaign_name'],
            niche_id=data['niche_id'],
            target_language=data.get('target_language', 'en'),
            search_queries=data.get('search_queries', []),
            product=product,
            sender_persona=sender,
            email_tone=data.get('email_tone', 'friendly_professional'),
            avoid_mentions=data.get('avoid_mentions', []),
            contacted_articles=data.get('contacted_articles', []),
            validation_gates=gates,
            max_articles_per_run=data.get('max_articles_per_run', 10),
            max_emails_per_day=data.get('max_emails_per_day', 20),
            context_module=data.get('context_module')
        )

    except Exception as e:
        print(f"Error loading campaign: {e}")
        return None


def get_active_campaign() -> str:
    """Get the active campaign ID."""
    # Check for .active_campaign file
    if os.path.exists('.active_campaign'):
        with open('.active_campaign', 'r') as f:
            return f.read().strip()

    # Return first campaign if only one exists
    campaigns = list_campaigns()
    if len(campaigns) == 1:
        return campaigns[0]['campaign_id']

    return None


def create_campaign_interactive():
    """Create a new campaign interactively."""
    print("\nCreate New Campaign")
    print("=" * 40)

    # Basic info
    campaign_id = input("Campaign ID (e.g., fitness_app_launch): ").strip()
    campaign_name = input("Campaign Name: ").strip()
    niche_id = input("Niche (e.g., fitness, tech, finance): ").strip()
    language = input("Target Language (en/it/es/etc) [en]: ").strip() or "en"

    # Product info
    print("\nProduct Information:")
    product_name = input("Product Name: ").strip()
    product_tagline = input("Product Tagline: ").strip()
    product_url = input("Product Website URL: ").strip()
    product_category = input("Product Category: ").strip()
    unique_value = input("Unique Value Proposition: ").strip()
    target_audience = input("Target Audience: ").strip()

    features = []
    print("Key Features (enter empty to finish):")
    while True:
        feature = input("  - ").strip()
        if not feature:
            break
        features.append(feature)

    # Sender persona
    print("\nSender Persona:")
    sender_name = input("Your Name: ").strip()
    sender_email = input("Your Email: ").strip()
    sender_title = input("Your Title: ").strip()
    sender_company = input("Your Company: ").strip()

    # Search queries
    print("\nSearch Queries (enter empty to finish):")
    queries = []
    while True:
        query = input("  - ").strip()
        if not query:
            break
        queries.append(query)

    # Build config
    config = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "niche_id": niche_id,
        "target_language": language,
        "search_queries": queries,
        "product": {
            "name": product_name,
            "tagline": product_tagline,
            "website_url": product_url,
            "category": product_category,
            "key_features": features,
            "unique_value_prop": unique_value,
            "target_audience": target_audience
        },
        "sender_persona": {
            "enabled": True,
            "name": sender_name,
            "email": sender_email,
            "title": sender_title,
            "company": sender_company,
            "preferred_greetings": ["Hi", "Hello"],
            "preferred_closings": ["Best", "Cheers"]
        },
        "email_tone": "friendly_professional",
        "avoid_mentions": [],
        "validation_gates": {
            "post_discovery": {"enabled": True, "blocking": True, "threshold": 0.5},
            "post_analysis": {"enabled": True, "blocking": True, "threshold": 0.5},
            "post_email": {"enabled": True, "blocking": True, "threshold": 0.6},
            "pre_send": {"enabled": True, "blocking": True, "threshold": 0.7}
        },
        "max_articles_per_run": 10,
        "max_emails_per_day": 20
    }

    # Save
    os.makedirs(CAMPAIGNS_DIR, exist_ok=True)
    path = os.path.join(CAMPAIGNS_DIR, f"{campaign_id}.json")

    with open(path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✓ Campaign created: {path}")
    print(f"\nTo generate outreach: python outreach.py generate --campaign {campaign_id}")


if __name__ == "__main__":
    main()
