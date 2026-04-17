#!/usr/bin/env python3
"""
Trigger.dev Python SDK Entry Point for Lisa Lead Follow-Up System.

This file defines all Trigger.dev tasks for the A/B testing automation.
Each task is a background job that runs on Trigger.dev's infrastructure
with full observability, retries, and scheduling.
"""
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from trigger_dev import task, TriggerContext, logger as trigger_logger

from config.settings import SystemConfig
from modules.orchestrator import Orchestrator
from modules.ab_testing import ABTestEngine
from modules.airtable_client import AirtableClient
from modules.response_tracker import ResponseTracker

# Configure logging to work with Trigger.dev
logging.basicConfig(
    level=getattr(logging, SystemConfig.LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)


# ============================================================================
# Task 1: Welcome Campaign
# ============================================================================

@task(
    id="welcome-campaign",
    name="Welcome Email Campaign",
    description="Send welcome emails to new leads with A/B testing",
    retries=3,
    timeout="10m",  # 10 minutes max
)
def welcome_campaign(context: TriggerContext, status_filter: str = "Intro-email"):
    """
    Run the welcome email campaign with A/B testing.
    
    - Fetches leads from Airtable with the specified status
    - Splits into groups of N (default 15, configured in .env)
    - Generates personalized emails using LLM with variation A/B/C
    - Sends emails via SMTP
    - Logs all activity to Airtable
    
    Args:
        status_filter: Airtable status to filter leads (default: "Intro-email")
    
    Returns:
        dict: Campaign results with group details and metrics
    """
    trigger_logger.info("🚀 Starting Welcome Campaign", {"status_filter": status_filter})
    
    try:
        orch = Orchestrator()
        groups = orch.run_welcome_campaign(status_filter=status_filter)
        
        # Build result summary
        results = {
            "campaign_type": "welcome",
            "status_filter": status_filter,
            "total_groups": len(groups),
            "total_leads": sum(len(g.leads) for g in groups),
            "total_emails_sent": sum(g.emails_sent for g in groups),
            "groups": [
                {
                    "group_number": g.group_number,
                    "lead_count": len(g.leads),
                    "emails_sent": g.emails_sent,
                    "welcome_variation": g.welcome_variation["id"],
                    "welcome_label": g.welcome_variation["label"],
                    "followup_variation": g.followup_variation["id"],
                    "response_rate": g.response_rate,
                }
                for g in groups
            ],
        }
        
        trigger_logger.info(
            "✅ Welcome Campaign Complete",
            {
                "total_groups": results["total_groups"],
                "total_emails_sent": results["total_emails_sent"],
            },
        )
        
        return results
        
    except Exception as e:
        trigger_logger.error("❌ Welcome Campaign Failed", {"error": str(e)})
        raise


# ============================================================================
# Task 2: Follow-Up Campaign
# ============================================================================

@task(
    id="followup-campaign",
    name="Follow-Up Email Campaign",
    description="Send 1-week follow-up emails with A/B testing",
    retries=3,
    timeout="10m",
)
def followup_campaign(context: TriggerContext, status_filter: str = "Pending-1-week"):
    """
    Run the follow-up email campaign with A/B testing.
    
    - Fetches leads from Airtable with "Pending-1-week" status
    - Splits into groups and assigns follow-up variations
    - Generates and sends follow-up emails
    - Logs to Airtable
    
    Args:
        status_filter: Airtable status to filter leads (default: "Pending-1-week")
    
    Returns:
        dict: Campaign results with group details and metrics
    """
    trigger_logger.info("📬 Starting Follow-Up Campaign", {"status_filter": status_filter})
    
    try:
        orch = Orchestrator()
        groups = orch.run_followup_campaign(status_filter=status_filter)
        
        results = {
            "campaign_type": "followup",
            "status_filter": status_filter,
            "total_groups": len(groups),
            "total_leads": sum(len(g.leads) for g in groups),
            "total_emails_sent": sum(g.emails_sent for g in groups),
            "groups": [
                {
                    "group_number": g.group_number,
                    "lead_count": len(g.leads),
                    "emails_sent": g.emails_sent,
                    "followup_variation": g.followup_variation["id"],
                    "followup_label": g.followup_variation["label"],
                    "response_rate": g.response_rate,
                }
                for g in groups
            ],
        }
        
        trigger_logger.info(
            "✅ Follow-Up Campaign Complete",
            {
                "total_groups": results["total_groups"],
                "total_emails_sent": results["total_emails_sent"],
            },
        )
        
        return results
        
    except Exception as e:
        trigger_logger.error("❌ Follow-Up Campaign Failed", {"error": str(e)})
        raise


# ============================================================================
# Task 3: Check Responses
# ============================================================================

@task(
    id="check-responses",
    name="Check Lead Responses",
    description="Check for lead responses and update A/B test metrics",
    retries=3,
    timeout="5m",
)
def check_responses(context: TriggerContext):
    """
    Check for responses from leads and update metrics.
    
    - Scans Airtable for leads with "Responded" status
    - Updates response rates per A/B group
    - Calculates average response times
    - Updates metrics in tracking state
    
    Returns:
        dict: Updated metrics for all groups
    """
    trigger_logger.info("🔍 Checking for lead responses...")
    
    try:
        orch = Orchestrator()
        metrics = orch.check_responses()
        
        # Find best performing group
        best_group = None
        best_rate = 0
        for m in metrics:
            if m["response_rate"] > best_rate:
                best_rate = m["response_rate"]
                best_group = m
        
        results = {
            "total_groups_tracked": len(metrics),
            "groups": metrics,
            "best_performing_group": {
                "group": best_group["group"] if best_group else None,
                "response_rate": best_group["response_rate"] if best_group else 0,
            } if best_group and best_rate > 0 else None,
        }
        
        trigger_logger.info(
            "✅ Response Check Complete",
            {
                "groups_checked": len(metrics),
                "best_response_rate": best_rate if best_group else 0,
            },
        )
        
        return results
        
    except Exception as e:
        trigger_logger.error("❌ Response Check Failed", {"error": str(e)})
        raise


# ============================================================================
# Task 4: Metrics Report
# ============================================================================

@task(
    id="metrics-report",
    name="A/B Test Metrics Report",
    description="Generate and log comprehensive A/B test metrics",
    retries=2,
    timeout="5m",
)
def metrics_report(context: TriggerContext):
    """
    Generate a comprehensive A/B test metrics report.
    
    Returns:
        dict: Full metrics report with winner analysis
    """
    trigger_logger.info("📊 Generating A/B Test Metrics Report...")
    
    try:
        airtable = AirtableClient()
        tracker = ResponseTracker(airtable)
        
        all_metrics = tracker.get_all_metrics()
        
        # Analyze winners by response rate
        if all_metrics:
            best_by_rate = max(all_metrics, key=lambda x: x["response_rate"])
            worst_by_rate = min(all_metrics, key=lambda x: x["response_rate"])
            
            # Calculate overall stats
            avg_response_rate = sum(m["response_rate"] for m in all_metrics) / len(all_metrics)
            total_emails = sum(m["emails_sent"] for m in all_metrics)
            total_responses = sum(m["responses"] for m in all_metrics)
            
            report = {
                "generated_at": context.run.id,
                "summary": {
                    "total_groups": len(all_metrics),
                    "total_emails_sent": total_emails,
                    "total_responses": total_responses,
                    "overall_response_rate": round((total_responses / total_emails) * 100, 2) if total_emails > 0 else 0,
                    "average_response_rate": round(avg_response_rate, 2),
                },
                "best_performing": {
                    "group": best_by_rate["group"],
                    "response_rate": best_by_rate["response_rate"],
                    "emails_sent": best_by_rate["emails_sent"],
                    "responses": best_by_rate["responses"],
                },
                "worst_performing": {
                    "group": worst_by_rate["group"],
                    "response_rate": worst_by_rate["response_rate"],
                },
                "all_groups": all_metrics,
            }
        else:
            report = {
                "generated_at": context.run.id,
                "summary": {
                    "total_groups": 0,
                    "total_emails_sent": 0,
                    "total_responses": 0,
                    "overall_response_rate": 0,
                },
                "message": "No metrics available yet. Run campaigns first.",
            }
        
        trigger_logger.info("✅ Metrics Report Generated", report["summary"])
        
        return report
        
    except Exception as e:
        trigger_logger.error("❌ Metrics Report Failed", {"error": str(e)})
        raise


# ============================================================================
# Task 5: Daily Batch (Recommended for Warming)
# ============================================================================

@task(
    id="daily-batch",
    name="Daily Batch Campaign",
    description="Send 3 emails (1 per A/B group) at 9am, 12pm, 3pm, 6pm",
    retries=3,
    timeout="10m",  # Short timeout - batch completes in ~1 minute
)
def daily_batch(
    context: TriggerContext,
    status_filter: str = "Intro-email",
    batch_size: int = 3,
):
    """
    Send a single batch: 3 emails (1 per A/B group).
    
    Designed to run 4 times daily at scheduled times (EST):
    - 9:00 AM EST (morning), 12:00 PM EST (noon), 3:00 PM EST (afternoon), 6:00 PM EST (evening)
    - Each batch sends 3 emails = 1 from each A/B group
    - Total: 12 emails/day with balanced A/B distribution
    
    Args:
        status_filter: Airtable status to filter leads
        batch_size: Emails per batch (default 3 = 1 per group)
    
    Returns:
        dict: Batch results with group distribution
    """
    trigger_logger.info(
        "📅 Starting Batch Send",
        {
            "batch_size": batch_size,
            "status_filter": status_filter,
            "schedule": "9am, 12pm, 3pm, 6pm daily",
        },
    )
    
    try:
        orch = Orchestrator()
        groups = orch.run_daily_batch(
            status_filter=status_filter,
            batch_size=batch_size,
        )
        
        # Build result
        results = {
            "campaign_type": "batch_send",
            "batch_size": batch_size,
            "total_groups": len(groups),
            "total_emails_sent": sum(g.emails_sent for g in groups),
            "groups": [
                {
                    "group_number": g.group_number,
                    "emails_sent": g.emails_sent,
                    "variation": g.welcome_variation["id"],
                    "response_rate": g.response_rate,
                }
                for g in groups
            ],
        }
        
        trigger_logger.info(
            "✅ Batch Complete",
            {
                "total_sent": results["total_emails_sent"],
                "groups": len(groups),
            },
        )
        
        return results
        
    except Exception as e:
        trigger_logger.error("❌ Batch Failed", {"error": str(e)})
        raise


# ============================================================================
# Task 6: Full Run (Welcome + Follow-Up)
# ============================================================================

@task(
    id="full-run",
    name="Full Campaign Run",
    description="Run both welcome and follow-up campaigns sequentially",
    retries=2,
    timeout="20m",
)
def full_run(context: TriggerContext):
    """
    Run both welcome and follow-up campaigns in sequence.
    
    This is useful for manual triggers or testing.
    
    Returns:
        dict: Results from both campaigns
    """
    trigger_logger.info("🚀 Starting Full Run (Welcome + Follow-Up)")
    
    results = {
        "welcome": None,
        "followup": None,
    }
    
    # Step 1: Welcome campaign
    trigger_logger.info("📧 Step 1: Welcome Campaign...")
    results["welcome"] = welcome_campaign(context)
    
    # Step 2: Follow-up campaign
    trigger_logger.info("📬 Step 2: Follow-Up Campaign...")
    results["followup"] = followup_campaign(context)
    
    trigger_logger.info("✅ Full Run Complete")
    
    return results


# ============================================================================
# Entry point for local testing
# ============================================================================

if __name__ == "__main__":
    # This allows running tasks locally for testing
    print("Trigger.dev tasks defined. Use 'trigger dev' or deploy to Trigger.dev cloud.")
    print("\nAvailable tasks:")
    print("  - welcome-campaign")
    print("  - followup-campaign")
    print("  - check-responses")
    print("  - metrics-report")
    print("  - full-run")
