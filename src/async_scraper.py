"""
Async Scraper for A View From My Seat

Uses asyncio and aiohttp for faster concurrent downloads.
"""

import asyncio
import json
import logging
import random
import re
from dataclasses import asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, quote_plus

import aiohttp
import aiofiles
from bs4 import BeautifulSoup

from .scraper import PhotoInfo

logger = logging.getLogger(__name__)


class AsyncAVFMSScraper:
    """Async scraper for A View From My Seat website."""

    BASE_URL = "https://aviewfrommyseat.com"

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(
        self,
        venue_name: str = "Madison+Square+Garden",
        output_dir: str = "output",
        delay_range: tuple = (0.5, 1.5),
        max_concurrent: int = 5,
        max_retries: int = 3,
    ):
        self.venue_name = venue_name
        self.venue_url_name = quote_plus(venue_name.replace("+", " "))
        self.output_dir = Path(output_dir)
        self.delay_range = delay_range
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries

        self.photos: list[PhotoInfo] = []
        self.sections: list[dict] = []

        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(
                headers=self.DEFAULT_HEADERS,
                timeout=timeout,
            )
        return self._session

    async def _random_delay(self):
        """Add random delay between requests."""
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)

    async def _fetch_page(self, url: str, retries: int = 0) -> Optional[str]:
        """Fetch a page with retry logic."""
        async with self._semaphore:
            try:
                await self._random_delay()
                session = await self._get_session()

                async with session.get(url) as response:
                    if response.status == 403:
                        logger.warning(f"Got 403 for {url}")
                        return None
                    response.raise_for_status()
                    return await response.text()

            except aiohttp.ClientError as e:
                if retries < self.max_retries:
                    wait_time = 2 ** retries
                    logger.warning(f"Request failed, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    return await self._fetch_page(url, retries + 1)
                logger.error(f"Failed to fetch {url}: {e}")
                return None

    async def get_sections(self) -> list[dict]:
        """Get all sections for the venue."""
        url = f"{self.BASE_URL}/venue/{self.venue_url_name}/sections/"
        logger.info(f"Fetching sections from: {url}")

        html = await self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        sections = []

        section_pattern = re.compile(r'/venue/[^/]+/section-([^/]+)/?')

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            match = section_pattern.search(href)
            if match:
                section_id = match.group(1)
                section_url = urljoin(self.BASE_URL, href)

                sections.append({
                    "id": section_id,
                    "name": link.get_text(strip=True) or section_id,
                    "url": section_url,
                })

        # Deduplicate
        seen = set()
        unique = []
        for s in sections:
            if s["id"] not in seen:
                seen.add(s["id"])
                unique.append(s)

        self.sections = unique
        logger.info(f"Found {len(self.sections)} sections")
        return self.sections

    async def get_section_photos(self, section: dict) -> list[PhotoInfo]:
        """Get photos for a section."""
        section_id = section["id"]
        photos = []
        page = 1

        while True:
            url = f"{section['url']}?page={page}" if page > 1 else section["url"]
            html = await self._fetch_page(url)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")
            page_photos = self._extract_photos(soup, section_id)

            if not page_photos:
                break

            photos.extend(page_photos)
            logger.info(f"Section {section_id} page {page}: {len(page_photos)} photos")

            if not soup.find("a", string=re.compile(r"Next|›", re.I)):
                break

            page += 1
            if page > 50:
                break

        return photos

    def _extract_photos(self, soup: BeautifulSoup, section_id: str) -> list[PhotoInfo]:
        """Extract photos from page."""
        photos = []
        photo_pattern = re.compile(r'/photo/(\d+)/[^/]+/section-([^/]+)/row-([^/]+)(?:/seat-([^/]+))?/?')

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            match = photo_pattern.search(href)
            if match:
                img = link.find("img")
                if img:
                    img_src = img.get("src") or img.get("data-src") or ""
                    if img_src:
                        if not img_src.startswith("http"):
                            img_src = urljoin(self.BASE_URL, img_src)

                        photos.append(PhotoInfo(
                            photo_id=match.group(1),
                            section=match.group(2),
                            row=match.group(3),
                            seat=match.group(4),
                            image_url=img_src,
                            page_url=urljoin(self.BASE_URL, href),
                        ))

        return photos

    async def download_photo(self, photo: PhotoInfo) -> Optional[Path]:
        """Download a single photo."""
        local_path = photo.get_local_path(self.output_dir)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if local_path.exists():
            return local_path

        async with self._semaphore:
            try:
                await self._random_delay()
                session = await self._get_session()

                async with session.get(photo.image_url) as response:
                    if response.status != 200:
                        return None

                    async with aiofiles.open(local_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)

                logger.info(f"Downloaded: {local_path.name}")
                return local_path

            except Exception as e:
                logger.error(f"Download failed for {photo.image_url}: {e}")
                return None

    async def download_all_photos(self, photos: list[PhotoInfo]) -> int:
        """Download all photos concurrently."""
        tasks = [self.download_photo(p) for p in photos]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is not None and not isinstance(r, Exception))

    async def scrape_all(
        self,
        download: bool = True,
        max_sections: int = None,
    ) -> list[PhotoInfo]:
        """Scrape all photos."""
        logger.info(f"Starting async scrape for: {self.venue_name}")

        sections = await self.get_sections()
        if not sections:
            return []

        if max_sections:
            sections = sections[:max_sections]

        # Scrape sections concurrently
        tasks = [self.get_section_photos(s) for s in sections]
        results = await asyncio.gather(*tasks)

        all_photos = []
        for photos in results:
            all_photos.extend(photos)

        self.photos = all_photos
        logger.info(f"Found {len(all_photos)} total photos")

        if download:
            count = await self.download_all_photos(all_photos)
            logger.info(f"Downloaded {count} photos")

        self.save_metadata()
        return all_photos

    def save_metadata(self):
        """Save metadata to JSON."""
        metadata = {
            "venue": self.venue_name,
            "total_photos": len(self.photos),
            "sections": len(self.sections),
            "photos": [asdict(p) for p in self.photos],
        }

        with open(self.output_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # Summary by section
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

        with open(self.output_dir / "summary_by_section.json", "w") as f:
            json.dump(summary, f, indent=2)

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def main():
    """Main async entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Async AVFMS Scraper")
    parser.add_argument("--venue", default="Madison+Square+Garden")
    parser.add_argument("--output", default="output")
    parser.add_argument("--max-sections", type=int)
    parser.add_argument("--max-concurrent", type=int, default=5)
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    async with AsyncAVFMSScraper(
        venue_name=args.venue,
        output_dir=args.output,
        max_concurrent=args.max_concurrent,
    ) as scraper:
        photos = await scraper.scrape_all(
            download=not args.no_download,
            max_sections=args.max_sections,
        )

    print(f"\nComplete! Found {len(photos)} photos")


if __name__ == "__main__":
    asyncio.run(main())
