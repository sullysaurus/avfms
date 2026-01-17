"""
A View From My Seat Scraper

Scrapes photos from aviewfrommyseat.com for a given venue
and organizes them by section, row, and seat.
"""

import os
import re
import json
import time
import random
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urljoin, quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class PhotoInfo:
    """Information about a photo from the venue."""
    photo_id: str
    section: str
    row: Optional[str]
    seat: Optional[str]
    image_url: str
    page_url: str
    event: Optional[str] = None
    contributor: Optional[str] = None

    def get_local_path(self, base_dir: Path) -> Path:
        """Get the local file path for this photo."""
        section_dir = f"section_{self.section}"
        row_part = f"row_{self.row}" if self.row else "row_unknown"
        seat_part = f"seat_{self.seat}" if self.seat else ""

        # Create filename from photo_id and original extension
        ext = Path(self.image_url).suffix or ".jpg"
        if seat_part:
            filename = f"{section_dir}_{row_part}_{seat_part}_{self.photo_id}{ext}"
        else:
            filename = f"{section_dir}_{row_part}_{self.photo_id}{ext}"

        return base_dir / section_dir / row_part / filename


class AVFMSScraper:
    """Scraper for A View From My Seat website."""

    BASE_URL = "https://aviewfrommyseat.com"

    # Browser-like headers to avoid 403 errors
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    def __init__(
        self,
        venue_name: str = "Madison+Square+Garden",
        output_dir: str = "output",
        delay_range: tuple = (1.0, 3.0),
        max_retries: int = 3,
        use_selenium: bool = False,
    ):
        self.venue_name = venue_name
        self.venue_url_name = quote_plus(venue_name.replace("+", " "))
        self.output_dir = Path(output_dir)
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.use_selenium = use_selenium

        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)

        self.driver = None
        self.photos: list[PhotoInfo] = []
        self.sections: list[dict] = []

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _random_delay(self):
        """Add a random delay between requests to be respectful."""
        delay = random.uniform(*self.delay_range)
        time.sleep(delay)

    def _get_page(self, url: str, retries: int = 0) -> Optional[str]:
        """Fetch a page with retry logic."""
        try:
            if self.use_selenium and self.driver:
                return self._get_page_selenium(url)

            self._random_delay()
            response = self.session.get(url, timeout=30)

            if response.status_code == 403:
                logger.warning(f"Got 403 for {url}, trying with Selenium...")
                if not self.use_selenium:
                    self._init_selenium()
                    self.use_selenium = True
                    return self._get_page_selenium(url)

            response.raise_for_status()
            return response.text

        except requests.RequestException as e:
            if retries < self.max_retries:
                wait_time = 2 ** retries
                logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
                return self._get_page(url, retries + 1)
            logger.error(f"Failed to fetch {url} after {self.max_retries} retries: {e}")
            return None

    def _init_selenium(self):
        """Initialize Selenium WebDriver as fallback."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument(f"user-agent={self.DEFAULT_HEADERS['User-Agent']}")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("Selenium WebDriver initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Selenium: {e}")
            raise

    def _get_page_selenium(self, url: str) -> Optional[str]:
        """Fetch page using Selenium."""
        try:
            self._random_delay()
            self.driver.get(url)
            time.sleep(2)  # Wait for JS to load
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Selenium failed to fetch {url}: {e}")
            return None

    def get_sections(self) -> list[dict]:
        """Get all sections for the venue."""
        url = f"{self.BASE_URL}/venue/{self.venue_url_name}/sections/"
        logger.info(f"Fetching sections from: {url}")

        html = self._get_page(url)
        if not html:
            logger.error("Failed to fetch sections page")
            return []

        soup = BeautifulSoup(html, "lxml")
        sections = []

        # Look for section links - they typically have patterns like /venue/Name/section-XXX/
        section_pattern = re.compile(r'/venue/[^/]+/section-([^/]+)/?')

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            match = section_pattern.search(href)
            if match:
                section_id = match.group(1)
                section_name = link.get_text(strip=True) or section_id
                section_url = urljoin(self.BASE_URL, href)

                sections.append({
                    "id": section_id,
                    "name": section_name,
                    "url": section_url,
                })

        # Deduplicate by section ID
        seen = set()
        unique_sections = []
        for s in sections:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique_sections.append(s)

        self.sections = unique_sections
        logger.info(f"Found {len(self.sections)} sections")
        return self.sections

    def get_section_photos(self, section: dict) -> list[PhotoInfo]:
        """Get all photos for a specific section."""
        section_id = section["id"]
        section_url = section["url"]
        logger.info(f"Fetching photos for section {section_id}")

        photos = []
        page = 1

        while True:
            # Handle pagination
            if page > 1:
                url = f"{section_url}?page={page}"
            else:
                url = section_url

            html = self._get_page(url)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")
            page_photos = self._extract_photos_from_page(soup, section_id)

            if not page_photos:
                break

            photos.extend(page_photos)
            logger.info(f"Section {section_id}, page {page}: found {len(page_photos)} photos")

            # Check for next page
            next_link = soup.find("a", string=re.compile(r"Next|›|>>", re.I))
            if not next_link:
                break

            page += 1

            # Safety limit
            if page > 50:
                logger.warning(f"Reached page limit for section {section_id}")
                break

        return photos

    def _extract_photos_from_page(self, soup: BeautifulSoup, section_id: str) -> list[PhotoInfo]:
        """Extract photo information from a page."""
        photos = []

        # Pattern for photo page URLs
        photo_pattern = re.compile(r'/photo/(\d+)/[^/]+/section-([^/]+)/row-([^/]+)(?:/seat-([^/]+))?/?')

        # Find all photo links
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            match = photo_pattern.search(href)
            if match:
                photo_id = match.group(1)
                section = match.group(2)
                row = match.group(3)
                seat = match.group(4)

                # Find the image within the link
                img = link.find("img")
                if img:
                    img_src = img.get("src") or img.get("data-src") or ""
                    if img_src:
                        # Convert thumbnail to full image if needed
                        img_url = self._get_full_image_url(img_src)
                        page_url = urljoin(self.BASE_URL, href)

                        photos.append(PhotoInfo(
                            photo_id=photo_id,
                            section=section,
                            row=row,
                            seat=seat,
                            image_url=img_url,
                            page_url=page_url,
                        ))

        # Also look for photo containers/cards
        for container in soup.find_all(["div", "article"], class_=re.compile(r"photo|image|gallery", re.I)):
            link = container.find("a", href=True)
            img = container.find("img")

            if link and img:
                href = link.get("href", "")
                match = photo_pattern.search(href)
                if match:
                    photo_id = match.group(1)
                    section = match.group(2)
                    row = match.group(3)
                    seat = match.group(4)

                    img_src = img.get("src") or img.get("data-src") or ""
                    if img_src:
                        img_url = self._get_full_image_url(img_src)
                        page_url = urljoin(self.BASE_URL, href)

                        # Check for duplicates
                        if not any(p.photo_id == photo_id for p in photos):
                            photos.append(PhotoInfo(
                                photo_id=photo_id,
                                section=section,
                                row=row,
                                seat=seat,
                                image_url=img_url,
                                page_url=page_url,
                            ))

        return photos

    def _get_full_image_url(self, thumbnail_url: str) -> str:
        """Convert thumbnail URL to full image URL."""
        # Common patterns for thumbnail -> full image conversion
        full_url = thumbnail_url

        # Remove common thumbnail indicators
        full_url = re.sub(r'_thumb\.(jpg|jpeg|png|gif)', r'.\1', full_url, flags=re.I)
        full_url = re.sub(r'-thumb\.(jpg|jpeg|png|gif)', r'.\1', full_url, flags=re.I)
        full_url = re.sub(r'/thumbs?/', '/photos/', full_url)
        full_url = re.sub(r'/small/', '/large/', full_url)
        full_url = re.sub(r'/medium/', '/large/', full_url)

        # Ensure absolute URL
        if not full_url.startswith("http"):
            full_url = urljoin(self.BASE_URL, full_url)

        return full_url

    def get_photo_details(self, photo: PhotoInfo) -> PhotoInfo:
        """Fetch additional details for a photo from its page."""
        html = self._get_page(photo.page_url)
        if not html:
            return photo

        soup = BeautifulSoup(html, "lxml")

        # Try to find better quality image
        main_img = soup.find("img", {"id": re.compile(r"main|photo|image", re.I)})
        if not main_img:
            main_img = soup.find("img", class_=re.compile(r"main|photo|image|full", re.I))
        if not main_img:
            # Look for the largest image
            images = soup.find_all("img")
            for img in images:
                src = img.get("src", "")
                if "photo" in src.lower() or "upload" in src.lower():
                    main_img = img
                    break

        if main_img:
            src = main_img.get("src") or main_img.get("data-src")
            if src:
                photo.image_url = self._get_full_image_url(src)

        # Try to find event name
        event_elem = soup.find(string=re.compile(r"Event:", re.I))
        if event_elem:
            parent = event_elem.find_parent()
            if parent:
                photo.event = parent.get_text(strip=True).replace("Event:", "").strip()

        # Try to find contributor
        contributor_elem = soup.find(string=re.compile(r"Shared by|Posted by|Contributed by", re.I))
        if contributor_elem:
            parent = contributor_elem.find_parent()
            if parent:
                text = parent.get_text(strip=True)
                match = re.search(r"(?:Shared|Posted|Contributed) by\s+(\w+)", text, re.I)
                if match:
                    photo.contributor = match.group(1)

        return photo

    def download_photo(self, photo: PhotoInfo) -> Optional[Path]:
        """Download a photo and save it to the organized directory structure."""
        local_path = photo.get_local_path(self.output_dir)

        # Create directory structure
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.exists():
            logger.debug(f"Photo already exists: {local_path}")
            return local_path

        try:
            self._random_delay()
            response = self.session.get(photo.image_url, timeout=30, stream=True)
            response.raise_for_status()

            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Downloaded: {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"Failed to download {photo.image_url}: {e}")
            return None

    def scrape_all(self, download: bool = True, max_sections: int = None) -> list[PhotoInfo]:
        """Scrape all photos from all sections."""
        logger.info(f"Starting scrape for venue: {self.venue_name}")

        # Get all sections
        sections = self.get_sections()
        if not sections:
            logger.error("No sections found")
            return []

        if max_sections:
            sections = sections[:max_sections]
            logger.info(f"Limiting to {max_sections} sections")

        # Scrape each section
        all_photos = []
        for i, section in enumerate(sections):
            logger.info(f"Processing section {i+1}/{len(sections)}: {section['id']}")
            photos = self.get_section_photos(section)
            all_photos.extend(photos)

        self.photos = all_photos
        logger.info(f"Found {len(all_photos)} total photos")

        # Download photos if requested
        if download:
            logger.info("Downloading photos...")
            for i, photo in enumerate(all_photos):
                logger.info(f"Downloading {i+1}/{len(all_photos)}")
                self.download_photo(photo)

        # Save metadata
        self.save_metadata()

        return all_photos

    def save_metadata(self):
        """Save photo metadata to JSON file."""
        metadata = {
            "venue": self.venue_name,
            "total_photos": len(self.photos),
            "sections": len(self.sections),
            "photos": [asdict(p) for p in self.photos],
        }

        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Saved metadata to {metadata_path}")

        # Also create a summary by section
        summary = {}
        for photo in self.photos:
            section = photo.section
            if section not in summary:
                summary[section] = {"rows": {}}
            row = photo.row or "unknown"
            if row not in summary[section]["rows"]:
                summary[section]["rows"][row] = []
            summary[section]["rows"][row].append({
                "photo_id": photo.photo_id,
                "seat": photo.seat,
                "image_url": photo.image_url,
            })

        summary_path = self.output_dir / "summary_by_section.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Saved summary to {summary_path}")

    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


def main():
    """Main entry point for the scraper."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Scrape photos from A View From My Seat"
    )
    parser.add_argument(
        "--venue",
        default="Madison+Square+Garden",
        help="Venue name (default: Madison+Square+Garden)",
    )
    parser.add_argument(
        "--output",
        default="output",
        help="Output directory (default: output)",
    )
    parser.add_argument(
        "--max-sections",
        type=int,
        default=None,
        help="Maximum number of sections to scrape",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Don't download images, just collect metadata",
    )
    parser.add_argument(
        "--use-selenium",
        action="store_true",
        help="Use Selenium browser automation (slower but more reliable)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    with AVFMSScraper(
        venue_name=args.venue,
        output_dir=args.output,
        use_selenium=args.use_selenium,
    ) as scraper:
        photos = scraper.scrape_all(
            download=not args.no_download,
            max_sections=args.max_sections,
        )

    print(f"\nScraping complete!")
    print(f"Total photos found: {len(photos)}")
    print(f"Output directory: {args.output}")


if __name__ == "__main__":
    main()
