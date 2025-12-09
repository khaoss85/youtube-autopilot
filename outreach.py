#!/usr/bin/env python3
# Suppress urllib3 SSL warning before any imports
import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

"""
PR Outreach CLI - Media PR outreach automation.

Workflow:
    1. search   → Find relevant articles
    2. analyze  → Analyze articles for fit
    3. contacts → Extract author contacts
    4. draft    → Generate personalized emails
    5. review   → Review pending emails
    6. approve  → Approve for sending
    7. send     → Send approved emails

Usage:
    python outreach.py search <campaign> [--max 10]
    python outreach.py analyze <campaign>
    python outreach.py contacts <campaign>
    python outreach.py draft <campaign>
    python outreach.py review <campaign>
    python outreach.py show <outreach_id>
    python outreach.py approve <outreach_id>
    python outreach.py reject <outreach_id> --reason "..."
    python outreach.py send <outreach_id>
    python outreach.py send-all <campaign>
    python outreach.py status <campaign>
    python outreach.py campaigns
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


CAMPAIGNS_DIR = "campaigns"
DATA_DIR = "data/outreach"


def main():
    parser = argparse.ArgumentParser(
        description="PR Outreach CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow example:
  python outreach.py search arvo_gym --max 5
  python outreach.py analyze arvo_gym
  python outreach.py contacts arvo_gym
  python outreach.py draft arvo_gym
  python outreach.py review arvo_gym
  python outreach.py approve abc123
  python outreach.py send abc123
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # --- WORKFLOW COMMANDS ---

    # 1. Search
    search_p = subparsers.add_parser("search", help="Search for relevant articles")
    search_p.add_argument("campaign", help="Campaign ID")
    search_p.add_argument("--max", "-m", type=int, default=10, help="Max articles to find")
    search_p.add_argument("--query", "-q", help="Custom search query (optional)")

    # 2. Analyze
    analyze_p = subparsers.add_parser("analyze", help="Analyze found articles for fit")
    analyze_p.add_argument("campaign", help="Campaign ID")
    analyze_p.add_argument("--min-score", type=float, default=0.5, help="Min relevance score")

    # 3. Contacts
    contacts_p = subparsers.add_parser("contacts", help="Extract author contacts")
    contacts_p.add_argument("campaign", help="Campaign ID")

    # 4. Draft
    draft_p = subparsers.add_parser("draft", help="Generate email drafts")
    draft_p.add_argument("campaign", help="Campaign ID")
    draft_p.add_argument("--max", "-m", type=int, default=5, help="Max emails to draft")

    # 5. Review
    review_p = subparsers.add_parser("review", help="List emails pending review")
    review_p.add_argument("campaign", nargs="?", help="Campaign ID (optional)")

    # 6. Show
    show_p = subparsers.add_parser("show", help="Show email details")
    show_p.add_argument("outreach_id", help="Outreach ID")

    # 7. Approve
    approve_p = subparsers.add_parser("approve", help="Approve email for sending")
    approve_p.add_argument("outreach_id", help="Outreach ID")
    approve_p.add_argument("--by", default="cli", help="Approver name/email")

    # 8. Reject
    reject_p = subparsers.add_parser("reject", help="Reject email")
    reject_p.add_argument("outreach_id", help="Outreach ID")
    reject_p.add_argument("--reason", "-r", required=True, help="Rejection reason")

    # 9. Send
    send_p = subparsers.add_parser("send", help="Send approved email")
    send_p.add_argument("outreach_id", help="Outreach ID")
    send_p.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # 10. Send-all
    sendall_p = subparsers.add_parser("send-all", help="Send all approved emails")
    sendall_p.add_argument("campaign", help="Campaign ID")
    sendall_p.add_argument("--force", "-f", action="store_true", help="Skip confirmation")

    # --- INFO COMMANDS ---

    # Status
    status_p = subparsers.add_parser("status", help="Show campaign status and stats")
    status_p.add_argument("campaign", help="Campaign ID")

    # Campaigns list
    subparsers.add_parser("campaigns", help="List all campaigns")

    # Campaign info
    info_p = subparsers.add_parser("info", help="Show campaign details")
    info_p.add_argument("campaign", help="Campaign ID")

    # List articles/contacts/emails
    list_p = subparsers.add_parser("list", help="List articles, contacts, or emails")
    list_p.add_argument("what", choices=["articles", "contacts", "emails"], help="What to list")
    list_p.add_argument("campaign", help="Campaign ID")
    list_p.add_argument("--status", "-s", help="Filter by status")

    # Run full pipeline
    run_p = subparsers.add_parser("run", help="Run full pipeline (search→draft)")
    run_p.add_argument("campaign", help="Campaign ID")
    run_p.add_argument("--max", "-m", type=int, default=3, help="Max articles to process")
    run_p.add_argument("--dry-run", action="store_true", help="Preview without saving")
    run_p.add_argument("--force-search", "-f", action="store_true",
                       help="Force new search even if unanalyzed articles exist")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route commands
    commands = {
        "search": cmd_search,
        "analyze": cmd_analyze,
        "contacts": cmd_contacts,
        "draft": cmd_draft,
        "review": cmd_review,
        "show": cmd_show,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "send": cmd_send,
        "send-all": cmd_send_all,
        "status": cmd_status,
        "campaigns": cmd_campaigns,
        "info": cmd_info,
        "list": cmd_list,
        "run": cmd_run,
    }

    handler = commands.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as e:
            print(f"Error: {e}")
            if os.getenv("DEBUG"):
                raise


# =============================================================================
# WORKFLOW COMMANDS
# =============================================================================

def cmd_search(args):
    """Search for relevant articles."""
    config = load_campaign(args.campaign)
    if not config:
        print(f"Campaign not found: {args.campaign}")
        return

    # Load existing articles to merge
    existing_articles = load_articles(args.campaign)
    existing_urls = {a.get('url') for a in existing_articles}

    print(f"\n🔍 Searching articles for: {config.campaign_name}")
    print(f"   Product: {config.product.name}")
    print(f"   Max results: {args.max}")
    if existing_articles:
        not_analyzed = [a for a in existing_articles if not a.get('analyzed')]
        print(f"   Existing: {len(existing_articles)} ({len(not_analyzed)} not analyzed)")
    print()

    from pr_outreach.agents.article_hunter import hunt_articles

    # Use custom query or campaign queries
    queries = [args.query] if args.query else config.search_queries

    print(f"   Queries: {len(queries)}")
    all_articles = hunt_articles(queries, config.product, config, max_results=args.max)
    print(f"   Found: {len(all_articles)} articles")

    # Dedupe and merge with existing
    new_count = 0
    for a in all_articles:
        url = a.url if hasattr(a, 'url') else a.get('url')
        if url and url not in existing_urls:
            existing_urls.add(url)
            # Convert to dict if needed
            if hasattr(a, 'model_dump'):
                article_dict = a.model_dump()
            else:
                article_dict = a if isinstance(a, dict) else {}
            article_dict['analyzed'] = False  # Mark as not analyzed
            existing_articles.append(article_dict)
            new_count += 1

    # Save merged articles
    save_articles(args.campaign, existing_articles)

    print(f"\n✓ Added {new_count} new articles (total: {len(existing_articles)})")
    print(f"  Saved to: data/outreach/{args.campaign}/articles.jsonl")
    print(f"\nNext: python outreach.py analyze {args.campaign}")


def cmd_analyze(args):
    """Analyze articles for fit."""
    config = load_campaign(args.campaign)
    if not config:
        print(f"Campaign not found: {args.campaign}")
        return

    articles = load_articles(args.campaign)
    if not articles:
        print(f"No articles found. Run 'search' first.")
        return

    print(f"\n📊 Analyzing {len(articles)} articles...")
    print(f"   Min relevance score: {args.min_score}")
    print()

    from pr_outreach.agents.article_analyzer import analyze_article
    from pr_outreach.core.schemas import ArticleCandidate

    analyzed = []
    for i, article in enumerate(articles):
        if article.get("analyzed"):
            print(f"   [{i+1}/{len(articles)}] Already analyzed: {article.get('title', 'N/A')[:40]}...")
            analyzed.append(article)
            continue

        print(f"   [{i+1}/{len(articles)}] Analyzing: {article.get('title', 'N/A')[:40]}...")

        try:
            # Convert dict to ArticleCandidate if needed
            article_obj = ArticleCandidate(**{k: v for k, v in article.items() if k in ArticleCandidate.model_fields})
            result = analyze_article(article_obj, config.product)

            # Update article dict with results
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()
            else:
                result_dict = result if isinstance(result, dict) else {}

            article["analyzed"] = True
            article["relevance_score"] = getattr(result, 'opportunity_score', 0) or result_dict.get("opportunity_score", 0)
            article["fit_reasoning"] = result_dict.get("fit_reasoning", "")
            article["positioning_angle"] = result_dict.get("positioning_angle", "")
            article["insertion_type"] = getattr(result, 'insertion_type', None) or result_dict.get("insertion_type")
            article["insertion_opportunities"] = result_dict.get("insertion_opportunities", [])

            score = article["relevance_score"]
            status = "✓" if score >= args.min_score else "✗"
            print(f"      {status} Score: {score:.2f}")

        except Exception as e:
            print(f"      ✗ Error analyzing: {e}")
            article["analyzed"] = True
            article["relevance_score"] = 0.0
            article["analysis_error"] = str(e)

        analyzed.append(article)

    # Save updated articles
    save_articles(args.campaign, analyzed)

    good = [a for a in analyzed if a.get("relevance_score", 0) >= args.min_score]
    print(f"\n✓ Analyzed {len(analyzed)} articles")
    print(f"  {len(good)} meet minimum score ({args.min_score})")
    print(f"\nNext: python outreach.py contacts {args.campaign}")


def cmd_contacts(args):
    """Extract author contacts."""
    config = load_campaign(args.campaign)
    if not config:
        print(f"Campaign not found: {args.campaign}")
        return

    articles = load_articles(args.campaign)
    good_articles = [a for a in articles if a.get("relevance_score", 0) >= 0.5]

    if not good_articles:
        print("No analyzed articles with good scores. Run 'analyze' first.")
        return

    print(f"\n👤 Extracting contacts from {len(good_articles)} articles...")
    print()

    from pr_outreach.services.author_finder import find_author_contacts

    contacts_found = 0
    for i, article in enumerate(good_articles):
        if article.get("author_email"):
            print(f"   [{i+1}/{len(good_articles)}] Already have: {article.get('author_name', 'Unknown')}")
            contacts_found += 1
            continue

        print(f"   [{i+1}/{len(good_articles)}] Finding: {article.get('author_name', 'Unknown')}...")

        contact = find_author_contacts(
            author_name=article.get("author_name", ""),
            domain=article.get("domain", ""),
            article_url=article.get("url", "")
        )

        if contact:
            article["author_email"] = contact.get("email")
            article["author_linkedin"] = contact.get("linkedin_url")
            article["author_twitter"] = contact.get("twitter_handle")
            article["contact_confidence"] = contact.get("email_confidence", 0)

            if contact.get("email"):
                contacts_found += 1
                print(f"      ✓ Found: {contact['email']}")
            else:
                print(f"      ✗ No email found")
        else:
            print(f"      ✗ Contact lookup failed")

    # Save updated
    save_articles(args.campaign, articles)

    print(f"\n✓ Found {contacts_found} contacts")
    print(f"\nNext: python outreach.py draft {args.campaign}")


def cmd_draft(args):
    """Generate email drafts."""
    config = load_campaign(args.campaign)
    if not config:
        print(f"Campaign not found: {args.campaign}")
        return

    articles = load_articles(args.campaign)
    ready = [a for a in articles
             if a.get("author_email")
             and a.get("relevance_score", 0) >= 0.5
             and not a.get("email_drafted")]

    if not ready:
        print("No articles ready for drafting.")
        print("Need: author email + relevance score >= 0.5 + not yet drafted")
        return

    to_draft = ready[:args.max]
    print(f"\n✉️  Drafting {len(to_draft)} emails...")
    print()

    from pr_outreach.agents.email_writer import write_outreach_email

    drafted = 0
    for i, article in enumerate(to_draft):
        print(f"   [{i+1}/{len(to_draft)}] {article['author_name']}...")

        email = write_outreach_email(
            article=article,
            product=config.product,
            sender=config.sender_persona,
            campaign_config=config
        )

        if email:
            # Save as outreach record
            outreach_id = save_outreach(args.campaign, article, email, config)
            article["email_drafted"] = True
            article["outreach_id"] = outreach_id
            drafted += 1
            print(f"      ✓ Draft saved: {outreach_id[:8]}...")
        else:
            print(f"      ✗ Failed to generate")

    # Update articles
    save_articles(args.campaign, articles)

    print(f"\n✓ Drafted {drafted} emails")
    print(f"\nNext: python outreach.py review {args.campaign}")


def cmd_review(args):
    """List emails pending review."""
    campaign_id = args.campaign

    emails = load_outreach(campaign_id, status="pending_review")

    if not emails:
        print("No emails pending review.")
        return

    print(f"\n📋 Pending Review ({len(emails)} emails)")
    print("=" * 70)

    for e in emails:
        print(f"\nID: {e['outreach_id'][:12]}")
        print(f"   To: {e['author_name']} <{e['author_email']}>")
        print(f"   Article: {e['article_title'][:50]}...")
        print(f"   Subject: {e['subject']}")
        print(f"   Score: {e.get('quality_score', 'N/A')}")

    print(f"\nTo view: python outreach.py show <id>")
    print(f"To approve: python outreach.py approve <id>")


def cmd_show(args):
    """Show email details."""
    email = find_outreach(args.outreach_id)

    if not email:
        print(f"Not found: {args.outreach_id}")
        return

    print("\n" + "=" * 70)
    print(f"ID: {email['outreach_id']}")
    print(f"Status: {email['status']}")
    print(f"Campaign: {email['campaign_id']}")
    print("=" * 70)

    print(f"\n📰 ARTICLE")
    print(f"   Title: {email['article_title']}")
    print(f"   URL: {email['article_url']}")
    print(f"   Score: {email.get('relevance_score', 'N/A')}")

    print(f"\n👤 AUTHOR")
    print(f"   Name: {email['author_name']}")
    print(f"   Email: {email['author_email']}")

    print(f"\n✉️  EMAIL")
    print(f"   Subject: {email['subject']}")
    print("-" * 70)
    print(email['body'])
    print("-" * 70)

    if email.get('positioning'):
        print(f"\n💡 POSITIONING")
        print(f"   {email['positioning'][:200]}...")

    print()
    if email['status'] == 'pending_review':
        print(f"Actions:")
        print(f"  python outreach.py approve {args.outreach_id}")
        print(f"  python outreach.py reject {args.outreach_id} --reason 'reason'")


def cmd_approve(args):
    """Approve email for sending."""
    email = find_outreach(args.outreach_id)

    if not email:
        print(f"Not found: {args.outreach_id}")
        return

    if email['status'] != 'pending_review':
        print(f"Cannot approve. Status: {email['status']}")
        return

    email['status'] = 'approved'
    email['approved_by'] = args.by
    email['approved_at'] = datetime.now().isoformat()

    update_outreach(email)

    print(f"✓ Approved: {args.outreach_id}")
    print(f"\nTo send: python outreach.py send {args.outreach_id}")


def cmd_reject(args):
    """Reject email."""
    email = find_outreach(args.outreach_id)

    if not email:
        print(f"Not found: {args.outreach_id}")
        return

    email['status'] = 'rejected'
    email['rejection_reason'] = args.reason
    email['rejected_at'] = datetime.now().isoformat()

    update_outreach(email)

    print(f"✓ Rejected: {args.outreach_id}")
    print(f"   Reason: {args.reason}")


def cmd_send(args):
    """Send approved email."""
    email = find_outreach(args.outreach_id)

    if not email:
        print(f"Not found: {args.outreach_id}")
        return

    if email['status'] != 'approved':
        print(f"Cannot send. Status: {email['status']}")
        print("Must be 'approved' to send.")
        return

    print(f"\n📤 Ready to send:")
    print(f"   To: {email['author_email']}")
    print(f"   Subject: {email['subject']}")

    if not args.force:
        confirm = input("\nSend? (y/N): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return

    from pr_outreach.services.email_sender import send_email

    success, result, provider = send_email(
        to_email=email['author_email'],
        subject=email['subject'],
        body=email['body']
    )

    if success:
        email['status'] = 'sent'
        email['sent_at'] = datetime.now().isoformat()
        email['message_id'] = result
        email['sent_via'] = provider
        update_outreach(email)

        print(f"✓ Sent via {provider}")
        print(f"   Message ID: {result}")
    else:
        print(f"✗ Failed: {result}")


def cmd_send_all(args):
    """Send all approved emails."""
    emails = load_outreach(args.campaign, status="approved")

    if not emails:
        print("No approved emails to send.")
        return

    print(f"\n📤 {len(emails)} emails ready to send")

    if not args.force:
        confirm = input(f"Send all {len(emails)}? (y/N): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return

    from pr_outreach.services.email_sender import send_email

    sent = 0
    failed = 0

    for email in emails:
        success, result, provider = send_email(
            to_email=email['author_email'],
            subject=email['subject'],
            body=email['body']
        )

        if success:
            email['status'] = 'sent'
            email['sent_at'] = datetime.now().isoformat()
            email['message_id'] = result
            update_outreach(email)
            sent += 1
            print(f"✓ {email['author_email']}")
        else:
            failed += 1
            print(f"✗ {email['author_email']}: {result}")

    print(f"\nSent: {sent}, Failed: {failed}")


def cmd_run(args):
    """Run full pipeline."""
    print(f"\n🚀 Running full pipeline for: {args.campaign}")
    print(f"   Max articles: {args.max}")
    if args.dry_run:
        print("   [DRY RUN]")
    print()

    # Check if there are unanalyzed articles
    existing_articles = load_articles(args.campaign)
    not_analyzed = [a for a in existing_articles if not a.get('analyzed')]

    # Reuse individual commands
    class Args:
        pass

    # Skip search if we have unanalyzed articles (unless --force-search)
    force_search = getattr(args, 'force_search', False)
    if not_analyzed and not force_search:
        print(f"⏭️  Skipping search: {len(not_analyzed)} articles pending analysis")
        print(f"   Use --force-search to search anyway\n")
    else:
        # Search
        search_args = Args()
        search_args.campaign = args.campaign
        search_args.max = args.max
        search_args.query = None
        cmd_search(search_args)

    # Analyze
    analyze_args = Args()
    analyze_args.campaign = args.campaign
    analyze_args.min_score = 0.5
    cmd_analyze(analyze_args)

    # Contacts
    contacts_args = Args()
    contacts_args.campaign = args.campaign
    cmd_contacts(contacts_args)

    # Draft
    if not args.dry_run:
        draft_args = Args()
        draft_args.campaign = args.campaign
        draft_args.max = args.max
        cmd_draft(draft_args)

    print(f"\n✓ Pipeline complete!")
    print(f"\nNext: python outreach.py review {args.campaign}")


# =============================================================================
# INFO COMMANDS
# =============================================================================

def cmd_status(args):
    """Show campaign status."""
    config = load_campaign(args.campaign)
    if not config:
        print(f"Campaign not found: {args.campaign}")
        return

    articles = load_articles(args.campaign)
    outreach = load_outreach(args.campaign)

    analyzed = [a for a in articles if a.get("analyzed")]
    with_contact = [a for a in articles if a.get("author_email")]

    pending = [o for o in outreach if o['status'] == 'pending_review']
    approved = [o for o in outreach if o['status'] == 'approved']
    sent = [o for o in outreach if o['status'] == 'sent']
    rejected = [o for o in outreach if o['status'] == 'rejected']

    print(f"\n📊 {config.campaign_name}")
    print("=" * 50)
    print(f"Product: {config.product.name}")
    print()
    print(f"PIPELINE STATUS")
    print(f"  Articles found:    {len(articles)}")
    print(f"  Articles analyzed: {len(analyzed)}")
    print(f"  Contacts found:    {len(with_contact)}")
    print()
    print(f"EMAILS")
    print(f"  Pending review:    {len(pending)}")
    print(f"  Approved:          {len(approved)}")
    print(f"  Sent:              {len(sent)}")
    print(f"  Rejected:          {len(rejected)}")
    print()

    if pending:
        print("Next: python outreach.py review", args.campaign)
    elif approved:
        print("Next: python outreach.py send-all", args.campaign)
    elif not articles:
        print("Next: python outreach.py search", args.campaign)


def cmd_campaigns(args):
    """List all campaigns."""
    campaigns = list_campaigns()

    if not campaigns:
        print("No campaigns found.")
        print(f"Create one in {CAMPAIGNS_DIR}/")
        return

    print("\n📂 Campaigns")
    print("=" * 50)

    for c in campaigns:
        print(f"\n  {c['campaign_id']}")
        print(f"    {c['campaign_name']}")
        print(f"    Product: {c['product_name']}")


def cmd_info(args):
    """Show campaign details."""
    config = load_campaign(args.campaign)
    if not config:
        print(f"Campaign not found: {args.campaign}")
        return

    print(f"\n📋 {config.campaign_name}")
    print("=" * 50)
    print(f"ID: {config.campaign_id}")
    print(f"Niche: {config.niche_id}")
    print(f"Language: {config.target_language}")
    print()
    print("PRODUCT")
    print(f"  Name: {config.product.name}")
    print(f"  Tagline: {config.product.tagline}")
    print(f"  URL: {config.product.website_url}")
    print()
    print("SENDER")
    print(f"  {config.sender_persona.name}")
    print(f"  {config.sender_persona.email}")
    print(f"  {config.sender_persona.title}")
    print()
    print("SEARCH QUERIES")
    for q in config.search_queries[:5]:
        print(f"  - {q}")
    if len(config.search_queries) > 5:
        print(f"  ... and {len(config.search_queries) - 5} more")


def cmd_list(args):
    """List articles, contacts, or emails."""
    if args.what == "articles":
        articles = load_articles(args.campaign)
        if not articles:
            print("No articles. Run 'search' first.")
            return

        print(f"\n📰 Articles ({len(articles)})")
        for a in articles:
            score = a.get('relevance_score', '-')
            if isinstance(score, float):
                score = f"{score:.2f}"
            print(f"  [{score}] {a['title'][:50]}...")
            print(f"       {a['url'][:60]}")

    elif args.what == "contacts":
        articles = load_articles(args.campaign)
        with_contact = [a for a in articles if a.get("author_email")]

        if not with_contact:
            print("No contacts found. Run 'contacts' first.")
            return

        print(f"\n👤 Contacts ({len(with_contact)})")
        for a in with_contact:
            print(f"  {a.get('author_name', 'Unknown')}")
            print(f"    {a['author_email']}")

    elif args.what == "emails":
        emails = load_outreach(args.campaign, status=args.status)

        if not emails:
            print("No emails. Run 'draft' first.")
            return

        print(f"\n✉️  Emails ({len(emails)})")
        for e in emails:
            status_icon = {
                'pending_review': '⏳',
                'approved': '✓',
                'sent': '📤',
                'rejected': '✗'
            }.get(e['status'], '?')
            print(f"  {status_icon} {e['outreach_id'][:8]} → {e['author_email']}")
            print(f"     {e['subject'][:50]}...")


# =============================================================================
# DATA HELPERS
# =============================================================================

def list_campaigns():
    """List available campaigns."""
    campaigns = []
    if not os.path.exists(CAMPAIGNS_DIR):
        return campaigns

    for f in os.listdir(CAMPAIGNS_DIR):
        if f.endswith('.json'):
            path = os.path.join(CAMPAIGNS_DIR, f)
            try:
                with open(path) as fp:
                    data = json.load(fp)
                    campaigns.append({
                        'campaign_id': data.get('campaign_id', f[:-5]),
                        'campaign_name': data.get('campaign_name', 'Unknown'),
                        'product_name': data.get('product', {}).get('name', 'Unknown')
                    })
            except:
                pass
    return campaigns


def load_campaign(campaign_id):
    """Load campaign config."""
    path = os.path.join(CAMPAIGNS_DIR, f"{campaign_id}.json")
    if not os.path.exists(path):
        return None

    try:
        from pr_outreach.core.schemas import CampaignConfig, ProductInfo, SenderPersona, ValidationGate

        with open(path) as f:
            data = json.load(f)

        product = ProductInfo(**data['product'])
        sender = SenderPersona(**data['sender_persona'])

        gates = {}
        for name, gdata in data.get('validation_gates', {}).items():
            gates[name] = ValidationGate(**gdata)

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


def get_data_path(campaign_id):
    """Get data directory for campaign."""
    path = os.path.join(DATA_DIR, campaign_id)
    os.makedirs(path, exist_ok=True)
    return path


def save_articles(campaign_id, articles):
    """Save articles to JSONL."""
    path = os.path.join(get_data_path(campaign_id), "articles.jsonl")
    with open(path, 'w') as f:
        for a in articles:
            if hasattr(a, 'model_dump'):
                a = a.model_dump()
            elif hasattr(a, '__dict__'):
                a = {k: v for k, v in a.__dict__.items() if not k.startswith('_')}
            f.write(json.dumps(a, default=str) + '\n')


def load_articles(campaign_id):
    """Load articles from JSONL."""
    path = os.path.join(get_data_path(campaign_id), "articles.jsonl")
    if not os.path.exists(path):
        return []

    articles = []
    with open(path) as f:
        for line in f:
            if line.strip():
                articles.append(json.loads(line))
    return articles


def save_outreach(campaign_id, article, email, config):
    """Save outreach record."""
    import uuid

    outreach_id = str(uuid.uuid4())[:12]

    record = {
        'outreach_id': outreach_id,
        'campaign_id': campaign_id,
        'status': 'pending_review',
        'created_at': datetime.now().isoformat(),

        # Article
        'article_title': article.get('title', ''),
        'article_url': article.get('url', ''),
        'relevance_score': article.get('relevance_score', 0),
        'positioning': article.get('positioning_angle', ''),

        # Author
        'author_name': article.get('author_name', ''),
        'author_email': article.get('author_email', ''),

        # Email
        'subject': email.get('subject', ''),
        'body': email.get('body', ''),
        'quality_score': email.get('quality_score', 0),
    }

    path = os.path.join(get_data_path(campaign_id), "outreach.jsonl")
    with open(path, 'a') as f:
        f.write(json.dumps(record, default=str) + '\n')

    return outreach_id


def load_outreach(campaign_id=None, status=None):
    """Load outreach records."""
    records = []

    if campaign_id:
        paths = [os.path.join(get_data_path(campaign_id), "outreach.jsonl")]
    else:
        # All campaigns
        paths = []
        if os.path.exists(DATA_DIR):
            for d in os.listdir(DATA_DIR):
                p = os.path.join(DATA_DIR, d, "outreach.jsonl")
                if os.path.exists(p):
                    paths.append(p)

    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    if line.strip():
                        r = json.loads(line)
                        if status is None or r.get('status') == status:
                            records.append(r)

    return records


def find_outreach(outreach_id):
    """Find outreach by ID."""
    if os.path.exists(DATA_DIR):
        for d in os.listdir(DATA_DIR):
            path = os.path.join(DATA_DIR, d, "outreach.jsonl")
            if os.path.exists(path):
                with open(path) as f:
                    for line in f:
                        if line.strip():
                            r = json.loads(line)
                            if r['outreach_id'] == outreach_id or r['outreach_id'].startswith(outreach_id):
                                r['_file'] = path
                                return r
    return None


def update_outreach(record):
    """Update outreach record."""
    path = record.pop('_file', None)
    if not path:
        path = os.path.join(get_data_path(record['campaign_id']), "outreach.jsonl")

    # Read all, update matching, rewrite
    records = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    if r['outreach_id'] == record['outreach_id']:
                        records.append(record)
                    else:
                        records.append(r)

    with open(path, 'w') as f:
        for r in records:
            f.write(json.dumps(r, default=str) + '\n')


if __name__ == "__main__":
    main()
