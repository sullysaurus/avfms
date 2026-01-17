"""
Configuration module for AVFMS scraper.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ScraperConfig:
    """Configuration for the scraper."""

    # Target venue
    venue_name: str = "Madison+Square+Garden"

    # Output settings
    output_dir: str = "output"

    # Request settings
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_retries: int = 3
    timeout: int = 30

    # Scraping limits
    max_sections: Optional[int] = None
    max_photos_per_section: Optional[int] = None

    # Browser settings
    use_selenium: bool = False
    headless: bool = True

    # Download settings
    download_images: bool = True
    skip_existing: bool = True

    # API settings (if available)
    api_key: Optional[str] = None

    # User agent rotation
    user_agents: list = field(default_factory=lambda: [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ])

    @classmethod
    def from_env(cls) -> "ScraperConfig":
        """Create config from environment variables."""
        return cls(
            venue_name=os.environ.get("AVFMS_VENUE", "Madison+Square+Garden"),
            output_dir=os.environ.get("AVFMS_OUTPUT", "output"),
            min_delay=float(os.environ.get("AVFMS_MIN_DELAY", "1.0")),
            max_delay=float(os.environ.get("AVFMS_MAX_DELAY", "3.0")),
            use_selenium=os.environ.get("AVFMS_USE_SELENIUM", "").lower() == "true",
            api_key=os.environ.get("AVFMS_API_KEY"),
        )


# Common venue mappings
VENUE_MAPPINGS = {
    "msg": "Madison+Square+Garden",
    "madison square garden": "Madison+Square+Garden",
    "yankee stadium": "Yankee+Stadium",
    "yankees": "Yankee+Stadium",
    "citi field": "Citi+Field",
    "mets": "Citi+Field",
    "barclays": "Barclays+Center",
    "barclays center": "Barclays+Center",
    "ubs arena": "UBS+Arena",
    "metlife": "MetLife+Stadium",
    "metlife stadium": "MetLife+Stadium",
}


def resolve_venue_name(name: str) -> str:
    """Resolve a venue name to its URL-friendly format."""
    lower_name = name.lower().strip()
    if lower_name in VENUE_MAPPINGS:
        return VENUE_MAPPINGS[lower_name]
    # Default: URL-encode the name
    return name.replace(" ", "+")
