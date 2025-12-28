"""Newsletter-specific text processor to remove boilerplate and non-meaningful content."""

import re

from service.text.text_processor import TextProcessor


class NewsletterCleaner(TextProcessor):
    """A text processor that removes newsletter boilerplate and non-meaningful content."""

    # Common newsletter header patterns
    HEADER_PATTERNS = [
        r"^.*?Newsletter\s*\n",  # Newsletter title
        r"Your customized.*?newsletter.*?\n",  # Customization message
        r"Hello,?\s*\n",  # Greeting
        r"Here is your customized.*?\n",  # Introduction line
    ]

    # Common newsletter footer patterns
    FOOTER_PATTERNS = [
        r"This email is a free service.*?$",
        r"You received this email because.*?$",
        r"If you do not wish to receive.*?unsubscribe.*?\.",
        r"You are subscribed as\s+[\w\.\-+]+@[\w\.\-]+\.[\w]+\s*\.",
        r"You may manage your subscription.*?\.",
        r"Story previews are generated using AI.*?\.",
        r"For the most complete and accurate information.*?\.",
        r"Read the full disclaimer\s*\.",
        r"©\s*\d{4}.*?All rights reserved\.",
        r"[\r\n]+\s*You may manage your subscription options from your.*?profile\s*\.",
    ]

    # Email addresses pattern
    EMAIL_PATTERN = r"\b[\w\.\-+]+@[\w\.\-]+\.[\w]+\b"

    # Excessive whitespace pattern
    WHITESPACE_PATTERN = r"\n{3,}"

    # Escape characters pattern
    ESCAPE_CHARS_PATTERN = r"\\r\\n|\\n|\\r"

    def __init__(self, remove_emails: bool = True, normalize_whitespace: bool = True):
        """Initialize the newsletter cleaner.

        Args:
            remove_emails (bool): Whether to remove email addresses. Defaults to True.
            normalize_whitespace (bool): Whether to normalize whitespace. Defaults to True.

        """
        self.remove_emails = remove_emails
        self.normalize_whitespace = normalize_whitespace

    def process_text(self, text: str, source: str) -> str:
        """Process newsletter text to remove boilerplate and non-meaningful content.

        Args:
            text (str): The input newsletter text to process.
            source (str): The source identifier of the text.

        Returns:
            str: The cleaned text with boilerplate removed.

        """
        if not text:
            return text

        cleaned_text = text

        # Remove escape characters first
        cleaned_text = re.sub(self.ESCAPE_CHARS_PATTERN, "\n", cleaned_text)

        # Remove header patterns (case insensitive, multiline)
        for pattern in self.HEADER_PATTERNS:
            cleaned_text = re.sub(
                pattern, "", cleaned_text, flags=re.IGNORECASE | re.MULTILINE
            )

        # Remove footer patterns (case insensitive, dotall to match across lines)
        for pattern in self.FOOTER_PATTERNS:
            cleaned_text = re.sub(
                pattern, "", cleaned_text, flags=re.IGNORECASE | re.DOTALL
            )

        # Remove email addresses if requested
        if self.remove_emails:
            cleaned_text = re.sub(self.EMAIL_PATTERN, "", cleaned_text)

        # Normalize whitespace if requested
        if self.normalize_whitespace:
            # Replace multiple newlines with double newline (paragraph separator)
            cleaned_text = re.sub(self.WHITESPACE_PATTERN, "\n\n", cleaned_text)

            # Remove leading/trailing whitespace from each line
            lines = [line.strip() for line in cleaned_text.split("\n")]
            cleaned_text = "\n".join(lines)

        # Final cleanup: remove leading/trailing whitespace
        cleaned_text = cleaned_text.strip()

        return cleaned_text


class AggressiveNewsletterCleaner(NewsletterCleaner):
    """A more aggressive newsletter cleaner that removes additional patterns."""

    # Additional patterns for aggressive cleaning
    AGGRESSIVE_PATTERNS = [
        r"^Science X Newsletter.*?for week \d+:?\s*\n",  # Specific newsletter headers
        r"unsubscribe here",
        r"manage your subscription",
        r"click here to",
        r"view this email in your browser",
        r"forward to a friend",
        r"update your preferences",
        r"privacy policy",
        r"terms of service",
        r"contact us at",
        r"follow us on",
        r"powered by.*?\n",
    ]

    def process_text(self, text: str, source: str) -> str:
        """Process newsletter text with aggressive cleaning rules.

        Args:
            text (str): The input newsletter text to process.
            source (str): The source identifier of the text.

        Returns:
            str: The aggressively cleaned text.

        """
        # First apply standard cleaning
        cleaned_text = super().process_text(text, source)

        # Apply aggressive patterns
        for pattern in self.AGGRESSIVE_PATTERNS:
            cleaned_text = re.sub(
                pattern, "", cleaned_text, flags=re.IGNORECASE | re.MULTILINE
            )

        # Final cleanup
        cleaned_text = cleaned_text.strip()

        return cleaned_text
