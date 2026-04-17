#!/usr/bin/env python3
"""
Lisa Lead Follow-Up System — Enhanced with A/B Testing

CLI entry point. Run `python main.py --help` for usage.
"""
import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

# Load environment variables from .env file
load_dotenv()

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import SystemConfig
from modules.orchestrator import Orchestrator
from modules.airtable_client import AirtableClient

console = Console()
airtable = AirtableClient()


def _setup_logging() -> None:
    """Configure logging to console and file."""
    log_dir = SystemConfig.LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "system.log"),
    ]
    logging.basicConfig(
        level=getattr(logging, SystemConfig.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


# ─── CLI Commands ─────────────────────────────────────────────────────────


@click.group()
def cli():
    """Lisa Lead Follow-Up System — A/B Testing Engine"""
    _setup_logging()


@cli.command()
@click.option(
    "--status",
    default="Intro-email",
    help="Airtable Status to filter leads for welcome emails.",
)
def welcome(status: str):
    """Send initial welcome emails with A/B testing."""
    console.print(
        f"\n[bold green]🚀 Starting Welcome Campaign[/bold green] "
        f"(filtering leads with status: '{status}')\n"
    )
    orch = Orchestrator()
    groups = orch.run_welcome_campaign(status_filter=status)
    _display_groups_table(groups, "Welcome Campaign Results")


@cli.command()
@click.option(
    "--status",
    default="Pending-1-week",
    help="Airtable Status to filter leads for follow-up emails.",
)
def followup(status: str):
    """Send 1-week follow-up emails with A/B testing."""
    console.print(
        f"\n[bold yellow]📬 Starting Follow-Up Campaign[/bold yellow] "
        f"(filtering leads with status: '{status}')\n"
    )
    orch = Orchestrator()
    groups = orch.run_followup_campaign(status_filter=status)
    _display_groups_table(groups, "Follow-Up Campaign Results")


@cli.command()
def check():
    """Check for responses and update metrics."""
    console.print("\n[bold cyan]🔍 Checking for responses...[/bold cyan]\n")
    orch = Orchestrator()
    metrics = orch.check_responses()
    _display_metrics_table(metrics)


@cli.command()
def check_replies():
    """Check IMAP inbox for email replies and update response tracking (runs daily at midnight)."""
    console.print("\n[bold cyan]📬 Checking IMAP for email replies...[/bold cyan]\n")
    from modules.response_tracker import ResponseTracker

    tracker = ResponseTracker(airtable)
    new_replies = tracker.check_replies()

    if new_replies > 0:
        console.print(f"[bold green]✓ Found {new_replies} new replies[/bold green]\n")
        # Display updated metrics
        all_metrics = tracker.get_all_metrics()
        _display_metrics_table(all_metrics)
    else:
        console.print("[dim]No new replies found.[/dim]\n")


@cli.command()
def metrics():
    """Display current A/B test metrics for all groups."""
    console.print("\n[bold magenta]📊 A/B Test Metrics[/bold magenta]\n")
    orch = Orchestrator()
    all_metrics = orch.tracker.get_all_metrics()
    _display_metrics_table(all_metrics)


@cli.command()
def full_run():
    """Run both welcome and follow-up campaigns sequentially."""
    console.print(
        "\n[bold green]🚀 Full Run: Welcome + Follow-Up Campaigns[/bold green]\n"
    )
    orch = Orchestrator()

    console.print("[bold]Step 1:[/bold] Welcome emails...")
    welcome_groups = orch.run_welcome_campaign()
    _display_groups_table(welcome_groups, "Welcome Results")

    console.print("\n[bold]Step 2:[/bold] Follow-up emails...")
    followup_groups = orch.run_followup_campaign()
    _display_groups_table(followup_groups, "Follow-Up Results")


@cli.command()
@click.option("--size", default=3, help="Emails per batch (default: 3 = 1 per A/B group)")
@click.option("--status", default="Intro-email", help="Airtable status to filter leads")
def daily_batch(size: int, status: str):
    """Send batch: 3 emails (1 per A/B group). Run at 9am, 12pm, 3pm, 6pm EST."""
    console.print(
        f"\n[bold blue]📅 Batch Send[/bold blue]\n"
        f"Sending {size} emails (1 per A/B group)\n"
        f"Scheduled: 9:00 AM, 12:00 PM, 3:00 PM, 6:00 PM EST\n"
    )
    
    # Log run start
    triggered_by = 'GITHUB_ACTIONS' if os.getenv('GITHUB_ACTIONS', 'false') == 'true' else 'MANUAL'
    run_record = airtable.log_run(
        action="daily-batch",
        status="STARTED",
        triggered_by=triggered_by,
        metadata={"size": size, "status_filter": status}
    )
    
    try:
        orch = Orchestrator()
        groups = orch.run_daily_batch(
            status_filter=status,
            batch_size=size,
        )
        _display_groups_table(groups, f"Batch Results ({size} emails)")
        
        # Log run completion
        airtable.update_run_status(run_record["id"], "COMPLETED")
    except Exception as e:
        airtable.update_run_status(run_record["id"], "FAILED")
        raise


# ─── Display helpers ──────────────────────────────────────────────────────


def _display_groups_table(groups, title: str) -> None:
    """Pretty-print A/B group results."""
    if not groups:
        console.print("[dim]No groups to display.[/dim]")
        return

    table = Table(title=title, show_header=True, header_style="bold blue")
    table.add_column("Group", style="cyan", justify="center")
    table.add_column("Leads", justify="center")
    table.add_column("Emails Sent", justify="center")
    table.add_column("Welcome Var.", style="green")
    table.add_column("Follow-Up Var.", style="yellow")
    table.add_column("Response Rate", justify="center")

    for g in groups:
        table.add_row(
            str(g.group_number),
            str(len(g.leads)),
            str(g.emails_sent),
            g.welcome_variation["id"],
            g.followup_variation["id"],
            f"{g.response_rate:.1f}%",
        )
    console.print(table)


def _display_metrics_table(metrics: list[dict]) -> None:
    """Pretty-print metrics across all groups."""
    if not metrics:
        console.print("[dim]No metrics available yet.[/dim]")
        return

    table = Table(
        title="A/B Test Metrics", show_header=True, header_style="bold magenta"
    )
    table.add_column("Group", style="cyan", justify="center")
    table.add_column("Emails Sent", justify="center")
    table.add_column("Responses", justify="center")
    table.add_column("Response Rate", justify="center", style="green")
    table.add_column("Avg Response Time", justify="center")

    for m in metrics:
        rate_style = "green" if m["response_rate"] > 20 else "yellow"
        table.add_row(
            str(m["group"]),
            str(m["emails_sent"]),
            str(m["responses"]),
            f"[{rate_style}]{m['response_rate']:.1f}%[/{rate_style}]",
            f"{m['avg_response_time_hours']:.1f}h",
        )
    console.print(table)

    # Highlight best performing group
    if metrics:
        best = max(metrics, key=lambda x: x["response_rate"])
        if best["response_rate"] > 0:
            console.print(
                f"\n[bold green]🏆 Best performing group: "
                f"Group {best['group']} with {best['response_rate']:.1f}% response rate[/bold green]"
            )


if __name__ == "__main__":
    cli()
