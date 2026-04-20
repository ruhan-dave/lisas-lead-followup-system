"""
LLM client for generating email content via OpenRouter.

Uses the OpenAI-compatible API provided by OpenRouter.
"""
import logging
import re

from openai import OpenAI

from config.settings import LLMConfig

logger = logging.getLogger(__name__)


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
    # Remove markdown italic (*text*)
    content = re.sub(r'\*(.*?)\*', r'\1', content)
    # Remove markdown headers (# text)
    content = re.sub(r'^#\s+', '', content, flags=re.MULTILINE)

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


def check_similarity(text1: str, text2: str, client) -> float:
    """
    Use LLM to check semantic similarity between two texts.

    Returns a similarity score between 0 and 1.
    """
    if not text1 or not text2:
        return 0.0

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
            model=client.model,
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

    def generate_email(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
    ) -> tuple[str, int]:
        """
        Generate an email body using the LLM.

        Returns:
            tuple: (generated_text, total_tokens_used)
        """
        logger.debug("Generating email with model=%s", self.model)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0
            logger.info(
                "LLM generated %d chars, %d tokens", len(content), tokens_used
            )
            # Clean up markdown and placeholders
            cleaned_content = clean_email_content(content.strip())
            logger.info("Cleaned email content: removed markdown and placeholders")
            return cleaned_content, tokens_used
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            raise
