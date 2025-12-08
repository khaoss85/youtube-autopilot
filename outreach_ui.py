#!/usr/bin/env python3
"""
PR Outreach Interactive UI - Simple terminal interface.

Usage:
    python outreach_ui.py [campaign]
"""

import os
import sys
from datetime import datetime

# Check for rich library
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
except ImportError:
    print("Install rich: pip install rich")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))

from outreach import (
    load_campaign, list_campaigns, load_articles, load_outreach,
    save_articles, save_outreach, find_outreach, update_outreach,
    get_data_path
)

console = Console()


def main():
    """Main interactive loop."""
    campaign_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not campaign_id:
        campaign_id = select_campaign()
        if not campaign_id:
            return

    config = load_campaign(campaign_id)
    if not config:
        console.print(f"[red]Campaign not found: {campaign_id}[/red]")
        return

    console.clear()
    show_header(config)

    while True:
        show_status(campaign_id, config)
        cmd = show_menu()

        if cmd == 'q':
            console.print("\n[dim]Bye![/dim]")
            break
        elif cmd == '1':
            run_search(campaign_id, config)
        elif cmd == '2':
            run_analyze(campaign_id, config)
        elif cmd == '3':
            run_contacts(campaign_id, config)
        elif cmd == '4':
            run_draft(campaign_id, config)
        elif cmd == '5':
            review_emails(campaign_id)
        elif cmd == '6':
            show_full_status(campaign_id, config)
        elif cmd == 'r':
            run_full_pipeline(campaign_id, config)
        elif cmd == 'c':
            console.clear()
            show_header(config)


def select_campaign():
    """Let user select a campaign."""
    campaigns = list_campaigns()

    if not campaigns:
        console.print("[red]No campaigns found.[/red]")
        return None

    console.print("\n[bold]Select Campaign:[/bold]\n")

    for i, c in enumerate(campaigns, 1):
        console.print(f"  [cyan]{i}[/cyan]) {c['campaign_name']}")
        console.print(f"      [dim]{c['product_name']}[/dim]")

    console.print()
    choice = console.input("[dim]Enter number (or q to quit):[/dim] ")

    if choice.lower() == 'q':
        return None

    try:
        idx = int(choice) - 1
        return campaigns[idx]['campaign_id']
    except (ValueError, IndexError):
        console.print("[red]Invalid choice[/red]")
        return None


def show_header(config):
    """Show campaign header."""
    console.print(Panel(
        f"[bold]{config.campaign_name}[/bold]\n"
        f"[dim]Product: {config.product.name}[/dim]",
        title="🎯 PR Outreach",
        border_style="blue"
    ))


def show_status(campaign_id, config):
    """Show quick status bar."""
    articles = load_articles(campaign_id)
    outreach = load_outreach(campaign_id)

    analyzed = len([a for a in articles if a.get("analyzed")])
    contacts = len([a for a in articles if a.get("author_email")])
    pending = len([o for o in outreach if o['status'] == 'pending_review'])
    approved = len([o for o in outreach if o['status'] == 'approved'])
    sent = len([o for o in outreach if o['status'] == 'sent'])

    status = (
        f"[cyan]Articles:[/cyan] {len(articles)} │ "
        f"[cyan]Analyzed:[/cyan] {analyzed} │ "
        f"[cyan]Contacts:[/cyan] {contacts} │ "
        f"[yellow]Pending:[/yellow] {pending} │ "
        f"[green]Approved:[/green] {approved} │ "
        f"[blue]Sent:[/blue] {sent}"
    )

    console.print(f"\n{status}\n")


def show_menu():
    """Show command menu and get input."""
    console.print("[bold]Commands:[/bold]")
    console.print("  [cyan]1[/cyan]) Search articles    [cyan]4[/cyan]) Draft emails")
    console.print("  [cyan]2[/cyan]) Analyze articles   [cyan]5[/cyan]) Review & approve")
    console.print("  [cyan]3[/cyan]) Find contacts      [cyan]6[/cyan]) Full status")
    console.print()
    console.print("  [green]r[/green]) Run full pipeline  [dim]c[/dim]) Clear  [dim]q[/dim]) Quit")
    console.print()

    return console.input("[bold]>[/bold] ").strip().lower()


def run_search(campaign_id, config):
    """Run article search with progress."""
    console.print("\n[bold]🔍 Searching articles...[/bold]\n")

    max_results = console.input("[dim]Max articles per query (default 5):[/dim] ").strip()
    max_results = int(max_results) if max_results.isdigit() else 5

    from pr_outreach.agents.article_hunter import search_articles

    all_articles = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for query in config.search_queries:
            task = progress.add_task(f"Searching: {query[:40]}...", total=None)

            try:
                articles = search_articles(query, config.product, max_results=max_results)
                all_articles.extend(articles)
                progress.update(task, description=f"[green]✓[/green] Found {len(articles)}: {query[:30]}...")
            except Exception as e:
                progress.update(task, description=f"[red]✗[/red] Error: {query[:30]}...")

            progress.stop_task(task)

    # Dedupe
    seen = set()
    unique = []
    for a in all_articles:
        url = a.url if hasattr(a, 'url') else a.get('url')
        if url and url not in seen:
            seen.add(url)
            unique.append(a)

    save_articles(campaign_id, unique)

    console.print(f"\n[green]✓ Found {len(unique)} unique articles[/green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


def run_analyze(campaign_id, config):
    """Run article analysis with progress."""
    articles = load_articles(campaign_id)
    to_analyze = [a for a in articles if not a.get("analyzed")]

    if not to_analyze:
        console.print("\n[yellow]All articles already analyzed.[/yellow]")
        console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    console.print(f"\n[bold]📊 Analyzing {len(to_analyze)} articles...[/bold]\n")

    from pr_outreach.agents.article_analyzer import analyze_article

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for article in to_analyze:
            title = article.get('title', 'Unknown')[:35]
            task = progress.add_task(f"Analyzing: {title}...", total=None)

            try:
                result = analyze_article(article, config.product)

                article["analyzed"] = True
                article["relevance_score"] = result.get("relevance_score", 0)
                article["fit_reasoning"] = result.get("reasoning", "")
                article["positioning_angle"] = result.get("positioning_angle", "")

                score = article["relevance_score"]
                icon = "✓" if score >= 0.5 else "✗"
                progress.update(task, description=f"[{'green' if score >= 0.5 else 'red'}]{icon}[/] {title}... ({score:.2f})")
            except Exception as e:
                progress.update(task, description=f"[red]✗[/red] Error: {title}...")

            progress.stop_task(task)

    save_articles(campaign_id, articles)

    good = len([a for a in articles if a.get("relevance_score", 0) >= 0.5])
    console.print(f"\n[green]✓ {good} articles with good fit[/green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


def run_contacts(campaign_id, config):
    """Find author contacts with progress."""
    articles = load_articles(campaign_id)
    to_find = [a for a in articles
               if a.get("relevance_score", 0) >= 0.5
               and not a.get("author_email")]

    if not to_find:
        console.print("\n[yellow]No articles need contact lookup.[/yellow]")
        console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    console.print(f"\n[bold]👤 Finding {len(to_find)} contacts...[/bold]\n")

    from pr_outreach.agents.contact_finder import find_author_contact

    found = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for article in to_find:
            name = article.get('author_name', 'Unknown')[:25]
            task = progress.add_task(f"Finding: {name}...", total=None)

            try:
                contact = find_author_contact(
                    author_name=article.get("author_name", ""),
                    article_url=article.get("url", ""),
                    domain=article.get("domain", "")
                )

                if contact and contact.get("email"):
                    article["author_email"] = contact.get("email")
                    article["author_linkedin"] = contact.get("linkedin")
                    article["author_twitter"] = contact.get("twitter")
                    found += 1
                    progress.update(task, description=f"[green]✓[/green] {name}: {contact['email']}")
                else:
                    progress.update(task, description=f"[yellow]−[/yellow] {name}: no email")
            except Exception as e:
                progress.update(task, description=f"[red]✗[/red] {name}: error")

            progress.stop_task(task)

    save_articles(campaign_id, articles)

    console.print(f"\n[green]✓ Found {found} contacts[/green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


def run_draft(campaign_id, config):
    """Generate email drafts with progress."""
    articles = load_articles(campaign_id)
    ready = [a for a in articles
             if a.get("author_email")
             and a.get("relevance_score", 0) >= 0.5
             and not a.get("email_drafted")]

    if not ready:
        console.print("\n[yellow]No articles ready for drafting.[/yellow]")
        console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    max_draft = console.input(f"[dim]How many to draft? (max {len(ready)}, default 3):[/dim] ").strip()
    max_draft = int(max_draft) if max_draft.isdigit() else 3
    to_draft = ready[:max_draft]

    console.print(f"\n[bold]✉️  Drafting {len(to_draft)} emails...[/bold]\n")

    from pr_outreach.agents.email_writer import write_outreach_email

    drafted = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        for article in to_draft:
            name = article.get('author_name', 'Unknown')[:25]
            task = progress.add_task(f"Drafting: {name}...", total=None)

            try:
                email = write_outreach_email(
                    article=article,
                    product=config.product,
                    sender=config.sender_persona,
                    campaign_config=config
                )

                if email:
                    outreach_id = save_outreach(campaign_id, article, email, config)
                    article["email_drafted"] = True
                    article["outreach_id"] = outreach_id
                    drafted += 1
                    progress.update(task, description=f"[green]✓[/green] {name}")
                else:
                    progress.update(task, description=f"[red]✗[/red] {name}: failed")
            except Exception as e:
                progress.update(task, description=f"[red]✗[/red] {name}: {str(e)[:20]}")

            progress.stop_task(task)

    save_articles(campaign_id, articles)

    console.print(f"\n[green]✓ Drafted {drafted} emails[/green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


def review_emails(campaign_id):
    """Interactive email review."""
    emails = load_outreach(campaign_id, status="pending_review")

    if not emails:
        console.print("\n[yellow]No emails pending review.[/yellow]")
        console.input("\n[dim]Press Enter to continue...[/dim]")
        return

    console.print(f"\n[bold]📋 {len(emails)} emails pending review[/bold]\n")

    for i, email in enumerate(emails):
        console.print(Panel(
            f"[bold]To:[/bold] {email['author_name']} <{email['author_email']}>\n"
            f"[bold]Article:[/bold] {email['article_title'][:50]}...\n"
            f"[bold]Subject:[/bold] {email['subject']}\n\n"
            f"[dim]{email['body'][:300]}...[/dim]",
            title=f"Email {i+1}/{len(emails)} - {email['outreach_id'][:8]}",
            border_style="cyan"
        ))

        console.print("\n[green]a[/green]) Approve  [red]r[/red]) Reject  [cyan]s[/cyan]) Skip  [dim]q[/dim]) Back to menu")
        action = console.input("\n[bold]>[/bold] ").strip().lower()

        if action == 'a':
            email['status'] = 'approved'
            email['approved_at'] = datetime.now().isoformat()
            email['_file'] = None  # Force lookup
            full_email = find_outreach(email['outreach_id'])
            if full_email:
                full_email['status'] = 'approved'
                full_email['approved_at'] = datetime.now().isoformat()
                update_outreach(full_email)
            console.print("[green]✓ Approved[/green]\n")
        elif action == 'r':
            reason = console.input("[dim]Reason:[/dim] ")
            full_email = find_outreach(email['outreach_id'])
            if full_email:
                full_email['status'] = 'rejected'
                full_email['rejection_reason'] = reason
                update_outreach(full_email)
            console.print("[red]✗ Rejected[/red]\n")
        elif action == 'q':
            break
        else:
            console.print("[dim]Skipped[/dim]\n")


def show_full_status(campaign_id, config):
    """Show detailed status table."""
    articles = load_articles(campaign_id)
    outreach = load_outreach(campaign_id)

    console.print("\n")

    # Pipeline table
    table = Table(title="Pipeline Status")
    table.add_column("Stage", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    total = len(articles)
    analyzed = len([a for a in articles if a.get("analyzed")])
    good_fit = len([a for a in articles if a.get("relevance_score", 0) >= 0.5])
    contacts = len([a for a in articles if a.get("author_email")])
    drafted = len([a for a in articles if a.get("email_drafted")])

    table.add_row("Articles Found", str(total), "✓" if total > 0 else "−")
    table.add_row("Analyzed", str(analyzed), "✓" if analyzed == total else f"{analyzed}/{total}")
    table.add_row("Good Fit (≥0.5)", str(good_fit), "✓" if good_fit > 0 else "−")
    table.add_row("Contacts Found", str(contacts), "✓" if contacts == good_fit else f"{contacts}/{good_fit}")
    table.add_row("Emails Drafted", str(drafted), "✓" if drafted > 0 else "−")

    console.print(table)

    # Email status table
    if outreach:
        table2 = Table(title="Email Status")
        table2.add_column("Status", style="cyan")
        table2.add_column("Count", justify="right")

        pending = len([o for o in outreach if o['status'] == 'pending_review'])
        approved = len([o for o in outreach if o['status'] == 'approved'])
        sent = len([o for o in outreach if o['status'] == 'sent'])
        rejected = len([o for o in outreach if o['status'] == 'rejected'])

        table2.add_row("Pending Review", str(pending))
        table2.add_row("Approved", str(approved))
        table2.add_row("Sent", str(sent))
        table2.add_row("Rejected", str(rejected))

        console.print(table2)

    console.input("\n[dim]Press Enter to continue...[/dim]")


def run_full_pipeline(campaign_id, config):
    """Run the full pipeline."""
    console.print("\n[bold]🚀 Running full pipeline...[/bold]")

    max_articles = console.input("[dim]Max articles (default 3):[/dim] ").strip()
    max_articles = int(max_articles) if max_articles.isdigit() else 3

    # Temporarily modify for pipeline
    original_queries = config.search_queries

    console.print("\n[bold cyan]Step 1/4: Search[/bold cyan]")
    run_search(campaign_id, config)

    console.print("\n[bold cyan]Step 2/4: Analyze[/bold cyan]")
    run_analyze(campaign_id, config)

    console.print("\n[bold cyan]Step 3/4: Contacts[/bold cyan]")
    run_contacts(campaign_id, config)

    console.print("\n[bold cyan]Step 4/4: Draft[/bold cyan]")
    run_draft(campaign_id, config)

    console.print("\n[bold green]✓ Pipeline complete![/bold green]")
    console.input("\n[dim]Press Enter to continue...[/dim]")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
