"""
LLM client for generating email content via OpenRouter.

Uses the OpenAI-compatible API provided by OpenRouter.
"""
import logging
import os
import re

from openai import OpenAI

from config.settings import LLMConfig

logger = logging.getLogger(__name__)


def load_brand_guidelines() -> str:
    """Load brand guidelines from brand.md file."""
    brand_file = os.path.join(os.path.dirname(__file__), '..', 'brand.md')
    if os.path.exists(brand_file):
        try:
            with open(brand_file, 'r') as f:
                content = f.read()
                logger.info("Loaded brand guidelines from brand.md")
                return content
        except Exception as e:
            logger.warning("Failed to load brand.md: %s", e)
    return ""


def parse_brand_sections(content: str) -> dict[str, str]:
    """Parse brand.md into sections by heading."""
    sections: dict[str, str] = {}
    current_heading = None
    current_lines: list[str] = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = line[3:].strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


# Core sections always injected (brand personality)
_CORE_SECTIONS = ["Brand Voice", "Tone Guidelines", "Email Style"]

# Intent keywords → relevant sections for selective retrieval
_INTENT_SECTION_MAP: dict[str, list[str]] = {
    "pricing": ["Key Value Propositions", "Product Categories", "How We Help"],
    "cost": ["Key Value Propositions", "Product Categories", "How We Help"],
    "price": ["Key Value Propositions", "Product Categories", "How We Help"],
    "install": ["How We Help", "Common Customer Pain Points", "Key Value Propositions"],
    "installation": ["How We Help", "Common Customer Pain Points", "Key Value Propositions"],
    "tool": ["How We Help", "Common Customer Pain Points"],
    "size": ["Product Categories", "Key Value Propositions"],
    "material": ["Product Categories", "Key Value Propositions", "Common Customer Pain Points"],
    "product": ["Product Categories", "Key Value Propositions", "How We Help"],
    "delivery": ["Key Value Propositions", "How We Help"],
    "shipping": ["Key Value Propositions", "How We Help"],
    "fast": ["Key Value Propositions", "How We Help"],
    "warranty": ["How We Help", "Common Customer Pain Points", "Key Value Propositions"],
    "durability": ["How We Help", "Common Customer Pain Points", "Key Value Propositions"],
    "weather": ["How We Help", "Common Customer Pain Points", "Key Value Propositions"],
    "rust": ["How We Help", "Common Customer Pain Points"],
    "fade": ["How We Help", "Common Customer Pain Points"],
    "bulk": ["Target Audience", "Key Value Propositions", "How We Help"],
    "contractor": ["Target Audience", "Key Value Propositions", "How We Help"],
    "builder": ["Target Audience", "Key Value Propositions", "How We Help"],
    "property manager": ["Target Audience", "Key Value Propositions", "How We Help"],
    "commercial": ["Target Audience", "Product Categories", "Key Value Propositions"],
    "multi-unit": ["Target Audience", "Product Categories", "Key Value Propositions"],
    "interior": ["Product Categories", "Target Audience"],
    "mailbox": ["Product Categories", "Key Value Propositions"],
    "light": ["Product Categories", "Key Value Propositions"],
    "illuminated": ["Product Categories", "Key Value Propositions"],
    "halo": ["Product Categories", "Key Value Propositions"],
    "lumi": ["Product Categories", "Key Value Propositions"],
    "plaques": ["Product Categories", "Key Value Propositions"],
    "house number": ["Product Categories", "Key Value Propositions"],
    "door number": ["Product Categories", "Key Value Propositions"],
    "night": ["Common Customer Pain Points", "Product Categories", "How We Help"],
    "visibility": ["Common Customer Pain Points", "Product Categories", "How We Help"],
    "dark": ["Common Customer Pain Points", "Product Categories", "How We Help"],
    "curb appeal": ["Company Overview", "Key Value Propositions"],
    "modern": ["Product Categories", "Key Value Propositions", "Common Customer Pain Points"],
    "design": ["Product Categories", "Key Value Propositions", "Common Customer Pain Points"],
    "aesthetic": ["Product Categories", "Common Customer Pain Points"],
    "look": ["Product Categories", "Common Customer Pain Points"],
    "diy": ["Key Value Propositions", "How We Help"],
    "easy": ["Key Value Propositions", "How We Help"],
    "simple": ["Key Value Propositions", "How We Help"],
    "order": ["Key Value Propositions", "How We Help"],
    "buy": ["Key Value Propositions", "How We Help"],
    "purchase": ["Key Value Propositions", "How We Help"],
    "custom": ["Key Value Propositions", "Product Categories"],
    "personalized": ["Key Value Propositions", "Product Categories"],
    "north american": ["Key Value Propositions", "Company Overview"],
    "made in usa": ["Key Value Propositions", "Company Overview"],
    "usa": ["Key Value Propositions", "Company Overview"],
}


def get_relevant_brand_context(intent_detail: str) -> str:
    """
    Selectively retrieve relevant brand sections based on intent.

    This is 'manual RAG' — no embeddings or vector DB needed.
    We parse the markdown by headings and inject only sections
    relevant to the customer's specific question or interest.
    """
    full_brand = load_brand_guidelines()
    if not full_brand:
        return ""

    sections = parse_brand_sections(full_brand)
    if not sections:
        return full_brand  # fallback to full dump if parsing fails

    # Always include core personality sections
    selected = set(_CORE_SECTIONS)

    # Add Company Overview as default context
    selected.add("Company Overview")

    # Map intent keywords to relevant sections
    intent_lower = intent_detail.lower()
    for keyword, section_list in _INTENT_SECTION_MAP.items():
        if keyword in intent_lower:
            selected.update(section_list)
            break  # Only match first keyword to avoid over-selection

    # Build context string
    parts: list[str] = []
    for heading in sections:
        if heading in selected:
            parts.append(f"## {heading}\n{sections[heading]}")

    context = "\n\n".join(parts)
    logger.info(
        "Selected %d/%d brand sections for intent '%s'",
        len(selected), len(sections), intent_detail
    )
    return context


def clean_email_content(content: str) -> str:
    """
    Clean up AI-generated email content.

    Removes:
    - Markdown formatting (bold **, italic *, etc.)
    - Placeholder links like [Link: ...]
    - Extra placeholders like [Your Name], [Company Name], [Website URL]
    """
    if not content:
        return content

    # Remove markdown bold (**text**)
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
    # Remove markdown italic (*text*) — but NOT standalone bullet points
    content = re.sub(r'(?<!\n)\*(.*?)\*(?!\n)', r'\1', content)
    # Remove markdown headers (# text)
    content = re.sub(r'^#\s+', '', content, flags=re.MULTILINE)

    # Remove standalone bullet points at line start (* item or - item)
    content = re.sub(r'^[\*\-]\s+', '', content, flags=re.MULTILINE)

    # Remove any "Subject:" line that the LLM mistakenly includes in the body
    content = re.sub(r'^Subject:.*\n?', '', content, flags=re.MULTILINE | re.IGNORECASE)

    # Remove placeholder links like [Link: ...] and [Link to ...]
    content = re.sub(r'\[Link: [^\]]+\]', '', content)
    content = re.sub(r'\[Link to [^\]]+\]', '', content)
    content = re.sub(r'\[Link\]', '', content)

    # Remove common placeholders
    placeholders = [
        r'\[Your Name\]',
        r'\[Company Name\]',
        r'\[Website URL\]',
        r'\[Your Company\]',
        r'\[Your Website\]',
        r'\[Company\]',
        r'\[Name\]',
        r'\[Email\]',
        r'\[Phone\]',
        r'\[Address\]',
        r'\[Position\]',
        r'\[Industry\]',
        r'\[Product\]',
        r'\[Service\]',
        r'\[Date\]',
        r'\[Time\]',
        r'\[Location\]',
        r'\[...\]',
        r'\[.*?\]',  # Catch-all for any [placeholder]
    ]
    for pattern in placeholders:
        content = re.sub(pattern, '', content)

    # Clean up extra whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)  # Multiple blank lines
    content = content.strip()

    return content


def check_similarity(text1: str, text2: str, client, model: str = None) -> float:
    """
    Use LLM to check semantic similarity between two texts.

    Returns a similarity score between 0 and 1.
    """
    if not text1 or not text2:
        return 0.0

    # Fallback to config model if not provided
    if model is None:
        model = LLMConfig.MODEL

    prompt = f"""Compare these two emails and rate their semantic similarity on a scale of 0 to 1, where:
- 1.0 = Identical meaning and style
- 0.9 = Very similar meaning and style (minor differences)
- 0.7 = Similar meaning but different style
- 0.5 = Related topics but different content
- 0.0 = Completely different

Email 1:
{text1}

Email 2:
{text2}

Return ONLY a number between 0 and 1 (e.g., 0.95, 0.87, 0.72). Do not include any other text."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0,
        )
        result = response.choices[0].message.content.strip()
        # Extract the number from the response
        score = float(re.search(r'[\d.]+', result).group())
        logger.info("Similarity check: %.2f", score)
        return min(max(score, 0.0), 1.0)  # Ensure within 0-1 range
    except Exception as e:
        logger.warning("Similarity check failed: %s", e)
        return 0.5  # Default to mid-range on failure


class LLMClient:
    """Generates email messages using an LLM through OpenRouter."""

    def __init__(self):
        if not LLMConfig.API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not set. Check your .env file.")
        self.client = OpenAI(
            api_key=LLMConfig.API_KEY,
            base_url=LLMConfig.BASE_URL,
        )
        self.model = LLMConfig.MODEL
        self.brand_guidelines = load_brand_guidelines()

    def generate_email(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
    ) -> tuple[str, int]:
        """
        Generate an email body using the LLM.

        Tries primary model first, then falls back through OPENROUTER_FALLBACK_MODELS
        on rate limits (429) or transient errors.

        Returns:
            tuple: (generated_text, total_tokens_used)
        """
        # Prepend brand guidelines to system prompt if available
        if self.brand_guidelines:
            enhanced_system_prompt = f"""BRAND GUIDELINES:
            {self.brand_guidelines}

            ORIGINAL SYSTEM PROMPT:
            {system_prompt}

            FORMATTING RULES (MUST FOLLOW):
            - Write ONLY the email body text. Do NOT include a "Subject:" line.
            - Do NOT use markdown formatting (**bold**, *italic*, # headers).
            - Do NOT use asterisk (*) or dash (-) bullet points. Use plain paragraphs or numbered lists instead.
            - Keep paragraphs short — 2 to 3 sentences maximum per paragraph. Use line breaks between paragraphs.
            - Keep the tone warm and personal, like a real email from a person.
            - Sign off as "Lisa" or "Lisa from My Address Number"."""
        else:
            enhanced_system_prompt = system_prompt

        models_to_try = [self.model] + LLMConfig.FALLBACK_MODELS

        last_error: Exception | None = None
        for model in models_to_try:
            logger.debug("Trying model=%s", model)
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": enhanced_system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.5,
                )
                content = response.choices[0].message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0
                logger.info(
                    "LLM (%s) generated %d chars, %d tokens",
                    model, len(content), tokens_used,
                )
                # Clean up markdown and placeholders
                cleaned_content = clean_email_content(content.strip())
                logger.info("Cleaned email content: removed markdown and placeholders")
                return cleaned_content, tokens_used
            except Exception as e:
                last_error = e
                # Retry on rate limits (429) and transient errors (5xx, timeout)
                err_str = str(e).lower()
                is_retryable = (
                    "429" in err_str
                    or "rate limit" in err_str
                    or "too many requests" in err_str
                    or "timeout" in err_str
                    or "5" in err_str and "error" in err_str
                )
                if is_retryable and model != models_to_try[-1]:
                    logger.warning(
                        "Model %s failed (retryable: %s), trying next fallback...",
                        model, e,
                    )
                    continue
                else:
                    logger.error("Model %s failed: %s", model, e)
                    break

        raise last_error or RuntimeError("All LLM models failed")
