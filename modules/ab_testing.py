"""
A/B Testing Engine.

Splits leads into groups of N and assigns each group a message variation.
Supports both initial welcome emails and follow-up emails.
"""
import logging
import math
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

from config.settings import ABTestConfig

logger = logging.getLogger(__name__)


# ── Message variation definitions ─────────────────────────────────────────

WELCOME_VARIATIONS: list[dict[str, str]] = [
    {
        "id": "welcome_A",
        "label": "Friendly & Benefits-Focused",
        "system_prompt": (
            "You are a warm, professional sales assistant for Lisa's company. "
            "Write a friendly welcome email that highlights specific product benefits "
            "and invite the lead to get a free quote or create an account."
        ),
        "user_prompt_template": (
            "Write a welcome email to {name} from {company}. "
            "Focus on how Lisa's products save time and reduce costs. "
            "End with a clear call-to-action: reply for a free quote or sign up at our website."
        ),
        "subject": "Welcome from Lisa — Let's save you time & money",
    },
    {
        "id": "welcome_B",
        "label": "Urgency & Social Proof",
        "system_prompt": (
            "You are a results-driven sales assistant for Lisa's company. "
            "Write a welcome email that uses social proof (client success stories) "
            "and create a sense of urgency to act now."
        ),
        "user_prompt_template": (
            "Write a welcome email to {name} from {company}. "
            "Mention that 200+ businesses already trust Lisa's products. "
            "Create urgency — e.g. limited-time onboarding support. "
            "End with a strong call-to-action to reply or sign up today."
        ),
        "subject": "Join 200+ businesses already seeing results with Lisa",
    },
    {
        "id": "welcome_C",
        "label": "Question-Led & Curiosity",
        "system_prompt": (
            "You are a consultative sales assistant for Lisa's company. "
            "Write a welcome email that opens with a thought-provoking question "
            "about the lead's pain points and positions Lisa's product as the answer."
        ),
        "user_prompt_template": (
            "Write a welcome email to {name} from {company}. "
            "Start with a question like 'Are you spending too much on X?' "
            "Then briefly explain how Lisa's product solves that. "
            "End by inviting them to reply or create a free account."
        ),
        "subject": "Quick question for you, {name}",
    },
    {
        "id": "welcome_D",
        "label": "Educational & Resource-Heavy",
        "system_prompt": (
            "You are an educational, value-first sales assistant for Lisa's company. "
            "Write a welcome email that shares a helpful resource or tip "
            "and positions Lisa's product as a tool to achieve similar results."
        ),
        "user_prompt_template": (
            "Write a welcome email to {name} from {company}. "
            "Share a quick industry tip or insight that could help them. "
            "Then explain how Lisa's product helps businesses apply this at scale. "
            "End with an invitation to learn more."
        ),
        "subject": "A helpful tip for {company}",
    },
    {
        "id": "welcome_E",
        "label": "Personal Story & Connection",
        "system_prompt": (
            "You are a relatable, story-telling sales assistant for Lisa's company. "
            "Write a welcome email that shares a brief personal story or experience "
            "that relates to the lead's challenges and builds connection."
        ),
        "user_prompt_template": (
            "Write a welcome email to {name} from {company}. "
            "Share a brief story about a challenge Lisa helped a client overcome. "
            "Make it relatable to their situation at {company}. "
            "End by offering to help them achieve similar results."
        ),
        "subject": "How Lisa helped a business like {company}",
    },
]

FOLLOWUP_VARIATIONS: list[dict[str, str]] = [
    {
        "id": "followup_A",
        "label": "Gentle Reminder + Value",
        "system_prompt": (
            "You are a patient, helpful sales assistant for Lisa's company. "
            "Write a follow-up email (1 week after the welcome) that gently reminds "
            "the lead of the value proposition and offers to answer any questions."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name} who received a welcome email 1 week ago "
            "but hasn't responded. Be friendly, remind them of the benefits, "
            "and offer a no-obligation call or demo."
        ),
        "subject": "Just checking in, {name} — any questions?",
    },
    {
        "id": "followup_B",
        "label": "FOMO & Case Study",
        "system_prompt": (
            "You are a persuasive sales assistant for Lisa's company. "
            "Write a follow-up email that shares a mini case study of a client "
            "who saw great results and emphasizes what the lead is missing out on."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name} who hasn't replied to the welcome email. "
            "Share a brief success story of a similar business that saved 30%% with Lisa. "
            "Create FOMO and end with a strong call-to-action."
        ),
        "subject": "Here's what {name} could be saving — a real client story",
    },
    {
        "id": "followup_C",
        "label": "Direct & Time-Limited Offer",
        "system_prompt": (
            "You are a direct, no-nonsense sales assistant for Lisa's company. "
            "Write a short follow-up email with a time-limited incentive to respond."
        ),
        "user_prompt_template": (
            "Write a short follow-up email to {name}. "
            "Be direct — mention this is a second reach-out. "
            "Offer a limited-time 15%% discount or free onboarding if they respond this week. "
            "Keep it under 100 words."
        ),
        "subject": "Last chance for your exclusive offer, {name}",
    },
    {
        "id": "followup_D",
        "label": "Social Proof Heavy",
        "system_prompt": (
            "You are a social-proof-focused sales assistant for Lisa's company. "
            "Write a follow-up email that emphasizes how many similar businesses use Lisa's products."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Mention that 50+ businesses in their industry use Lisa's products. "
            "Share one specific success metric. "
            "Ask if they'd like to see a demo of how it works."
        ),
        "subject": "Your competitors are already using this, {name}",
    },
    {
        "id": "followup_E",
        "label": "New Feature Announcement",
        "system_prompt": (
            "You are an enthusiastic sales assistant for Lisa's company. "
            "Write a follow-up email announcing a new feature or improvement."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Announce a new feature that directly addresses their pain points. "
            "Explain how this feature helps businesses like {company}. "
            "Offer to show them how it works."
        ),
        "subject": "New feature that could help {company}",
    },
    {
        "id": "followup_F",
        "label": "Industry Insight",
        "system_prompt": (
            "You are an industry-expert sales assistant for Lisa's company. "
            "Write a follow-up email sharing relevant industry news or trends."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Share a relevant industry trend or challenge. "
            "Explain how Lisa's product helps businesses navigate this. "
            "Ask if they're seeing similar challenges at {company}."
        ),
        "subject": "Industry trend affecting {company}",
    },
    {
        "id": "followup_G",
        "label": "Competitive Comparison",
        "system_prompt": (
            "You are a competitive sales assistant for Lisa's company. "
            "Write a follow-up email comparing Lisa's product favorably to alternatives."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Compare Lisa's product to common alternatives. "
            "Highlight 3 key advantages. "
            "Ask if they'd like a side-by-side comparison."
        ),
        "subject": "How Lisa compares to alternatives",
    },
    {
        "id": "followup_H",
        "label": "ROI Calculator",
        "system_prompt": (
            "You are a data-driven sales assistant for Lisa's company. "
            "Write a follow-up email focused on return on investment."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Explain how to calculate ROI for Lisa's product. "
            "Provide a simple example with realistic numbers. "
            "Offer to run a custom ROI analysis for {company}."
        ),
        "subject": "Calculate your ROI with Lisa",
    },
    {
        "id": "followup_I",
        "label": "Objection Handling",
        "system_prompt": (
            "You are an empathetic sales assistant for Lisa's company. "
            "Write a follow-up email addressing common objections proactively."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Address common concerns: cost, implementation time, training. "
            "Provide reassuring answers for each. "
            "Ask what concerns they might have."
        ),
        "subject": "Common questions about Lisa",
    },
    {
        "id": "followup_J",
        "label": "Testimonial Quote",
        "system_prompt": (
            "You are a testimonial-focused sales assistant for Lisa's company. "
            "Write a follow-up email featuring a client quote."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Include a compelling testimonial quote from a similar business. "
            "Explain the context and results. "
            "Ask if they'd like to hear more success stories."
        ),
        "subject": "What clients say about Lisa",
    },
    {
        "id": "followup_K",
        "label": "Implementation Ease",
        "system_prompt": (
            "You are a reassuring sales assistant for Lisa's company. "
            "Write a follow-up email emphasizing how easy implementation is."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Explain the simple 3-step implementation process. "
            "Mention average setup time is under 2 hours. "
            "Offer to guide them through the process."
        ),
        "subject": "Get started in under 2 hours",
    },
    {
        "id": "followup_L",
        "label": "Integration Benefits",
        "system_prompt": (
            "You are a technical sales assistant for Lisa's company. "
            "Write a follow-up email highlighting integrations."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "List popular tools Lisa integrates with. "
            "Explain how this saves time and reduces manual work. "
            "Ask what tools they currently use at {company}."
        ),
        "subject": "Lisa integrates with your tools",
    },
    {
        "id": "followup_M",
        "label": "Scalability Focus",
        "system_prompt": (
            "You are a growth-focused sales assistant for Lisa's company. "
            "Write a follow-up email emphasizing scalability."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Explain how Lisa scales with business growth. "
            "Mention clients who grew from 10 to 1000 users seamlessly. "
            "Ask about {company}'s growth plans."
        ),
        "subject": "Grow with Lisa",
    },
    {
        "id": "followup_N",
        "label": "Security & Compliance",
        "system_prompt": (
            "You are a security-conscious sales assistant for Lisa's company. "
            "Write a follow-up email emphasizing security features."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Highlight security certifications and compliance. "
            "Mention data protection measures. "
            "Ask if security is a priority for {company}."
        ),
        "subject": "Security first at Lisa",
    },
    {
        "id": "followup_O",
        "label": "Customer Support Emphasis",
        "system_prompt": (
            "You are a support-focused sales assistant for Lisa's company. "
            "Write a follow-up email highlighting customer support."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Describe the dedicated support team. "
            "Mention average response time under 2 hours. "
            "Offer to introduce them to their account manager."
        ),
        "subject": "Dedicated support for {company}",
    },
    {
        "id": "followup_P",
        "label": "Free Trial Focus",
        "system_prompt": (
            "You are a trial-focused sales assistant for Lisa's company. "
            "Write a follow-up email promoting a free trial."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Offer a 14-day free trial with no credit card required. "
            "Explain what they can test during the trial. "
            "Ask if they'd like to start today."
        ),
        "subject": "Try Lisa free for 14 days",
    },
    {
        "id": "followup_Q",
        "label": "Competitor Migration",
        "system_prompt": (
            "You are a migration-focused sales assistant for Lisa's company. "
            "Write a follow-up email about switching from competitors."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Explain how easy it is to switch from their current solution. "
            "Migrate data in under 1 day. "
            "Offer to handle the migration for them."
        ),
        "subject": "Switch from your current tool easily",
    },
    {
        "id": "followup_R",
        "label": "Team Collaboration",
        "system_prompt": (
            "You are a team-focused sales assistant for Lisa's company. "
            "Write a follow-up email about team collaboration features."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Describe how Lisa improves team collaboration. "
            "Mention shared workspaces and real-time updates. "
            "Ask about team size at {company}."
        ),
        "subject": "Better collaboration for your team",
    },
    {
        "id": "followup_S",
        "label": "Mobile Access",
        "system_prompt": (
            "You are a mobile-focused sales assistant for Lisa's company. "
            "Write a follow-up email about mobile app availability."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Describe the mobile app and its features. "
            "Explain how it enables work from anywhere. "
            "Ask if they have remote workers at {company}."
        ),
        "subject": "Lisa goes mobile",
    },
    {
        "id": "followup_T",
        "label": "Customization Options",
        "system_prompt": (
            "You are a customization-focused sales assistant for Lisa's company. "
            "Write a follow-up email about customization options."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Describe flexible customization options. "
            "Explain how Lisa adapts to specific workflows. "
            "Ask about {company}'s unique processes."
        ),
        "subject": "Lisa adapts to your workflow",
    },
    {
        "id": "followup_U",
        "label": "Analytics & Reporting",
        "system_prompt": (
            "You are an analytics-focused sales assistant for Lisa's company. "
            "Write a follow-up email about reporting features."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Describe powerful analytics and reporting. "
            "Mention customizable dashboards and automated reports. "
            "Ask what metrics matter most to {company}."
        ),
        "subject": "Data-driven insights with Lisa",
    },
    {
        "id": "followup_V",
        "label": "Automation Capabilities",
        "system_prompt": (
            "You are an automation-focused sales assistant for Lisa's company. "
            "Write a follow-up email about automation features."
        ),
        "user_prompt_template": (
            "Write a follow-up email to {name}. "
            "Describe automation capabilities that save time. "
            "Give examples of common automations. "
            "Ask what manual tasks they'd like to automate."
        ),
        "subject": "Automate your work with Lisa",
    },
    {
        "id": "followup_W",
        "label": "Final Nudge",
        "system_prompt": (
            "You are a polite but persistent sales assistant for Lisa's company. "
            "Write a final follow-up email after 3 weeks of no response."
        ),
        "user_prompt_template": (
            "Write a final follow-up email to {name}. "
            "Acknowledge they haven't responded but leave the door open. "
            "Offer to reach out again in 3 months if timing is better. "
            "Wish them well regardless."
        ),
        "subject": "Last check-in, {name}",
    },
]


# ── Data classes ──────────────────────────────────────────────────────────


@dataclass
class ABGroup:
    """Represents one A/B test group of leads."""

    group_number: int
    leads: list[dict[str, Any]]
    welcome_variation: dict[str, str]
    followup_variation: dict[str, str]
    # Tracking
    emails_sent: int = 0
    responses_received: int = 0
    response_times_seconds: list[float] = field(default_factory=list)

    @property
    def response_rate(self) -> float:
        """Response rate as a percentage (0-100)."""
        if self.emails_sent == 0:
            return 0.0
        return round((self.responses_received / self.emails_sent) * 100, 2)

    @property
    def avg_response_time_hours(self) -> float:
        """Average response time in hours."""
        if not self.response_times_seconds:
            return 0.0
        return round(
            sum(self.response_times_seconds) / len(self.response_times_seconds) / 3600,
            2,
        )


# ── Engine ────────────────────────────────────────────────────────────────


class ABTestEngine:
    """Splits leads into groups of N and assigns message variations."""

    def __init__(self, group_size: int = None):
        self.group_size = group_size or ABTestConfig.GROUP_SIZE
        self.welcome_variations, self.followup_variations = self._load_variations()

    def _load_variations(self):
        """Load custom prompts if they exist and are not expired (within 3 days), otherwise use defaults."""
        custom_path = os.path.join(
            os.path.dirname(__file__), '..', 'config', 'custom_prompts.json'
        )
        if os.path.exists(custom_path):
            try:
                with open(custom_path, 'r') as f:
                    data = json.load(f)

                # Check if custom prompts are expired (older than 3 days)
                expires_at = data.get("expires_at")
                if expires_at:
                    expiration_date = datetime.fromisoformat(expires_at)
                    if datetime.now() > expiration_date:
                        logger.info("Custom prompts expired (created: %s, expired: %s), using defaults",
                                   data.get("created_at"), expires_at)
                        return WELCOME_VARIATIONS, FOLLOWUP_VARIATIONS
                    else:
                        days_remaining = (expiration_date - datetime.now()).days
                        logger.info("Using custom prompts (valid for %d more days)", days_remaining)

                welcome = data.get("welcome", WELCOME_VARIATIONS)
                followup = data.get("followup", FOLLOWUP_VARIATIONS)
                logger.info("Loaded custom prompts from %s", custom_path)
                return welcome, followup
            except Exception as e:
                logger.warning("Failed to load custom prompts, using defaults: %s", e)
        return WELCOME_VARIATIONS, FOLLOWUP_VARIATIONS

    def create_groups(self, leads: list[dict[str, Any]]) -> list[ABGroup]:
        """
        Split leads into groups of `group_size` and assign each group
        a welcome + followup variation (round-robin across available variations).
        """
        num_groups = math.ceil(len(leads) / self.group_size)
        groups: list[ABGroup] = []

        for i in range(num_groups):
            start = i * self.group_size
            end = start + self.group_size
            chunk = leads[start:end]

            welcome_var = self.welcome_variations[i % len(self.welcome_variations)]
            followup_var = self.followup_variations[i % len(self.followup_variations)]

            group = ABGroup(
                group_number=i + 1,
                leads=chunk,
                welcome_variation=welcome_var,
                followup_variation=followup_var,
            )
            groups.append(group)

            logger.info(
                "Group %d: %d leads | welcome=%s | followup=%s",
                group.group_number,
                len(chunk),
                welcome_var["id"],
                followup_var["id"],
            )

        logger.info(
            "Created %d A/B test groups from %d leads (group size=%d)",
            len(groups),
            len(leads),
            self.group_size,
        )
        return groups
