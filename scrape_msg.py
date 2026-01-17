#!/usr/bin/env python3
"""
Madison Square Garden Photo Scraper

Quick script to scrape all photos from Madison Square Garden
and organize them by section, row, and seat.

Usage:
    python scrape_msg.py                    # Scrape all photos
    python scrape_msg.py --max-sections 5   # Test with 5 sections
    python scrape_msg.py --async            # Use async scraper (faster)
    python scrape_msg.py --no-download      # Only collect metadata
"""

import sys
import logging
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Scrape Madison Square Garden photos from A View From My Seat"
    )
    parser.add_argument(
        "--output", "-o",
        default="output/msg",
        help="Output directory (default: output/msg)",
    )
    parser.add_argument(
        "--max-sections",
        type=int,
        help="Maximum sections to scrape (for testing)",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Only collect metadata, don't download images",
    )
    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async scraper for faster downloads",
    )
    parser.add_argument(
        "--selenium",
        action="store_true",
        help="Use Selenium browser (slower but more reliable)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    venue = "Madison+Square+Garden"

    print("=" * 60)
    print("Madison Square Garden Photo Scraper")
    print("=" * 60)
    print(f"Venue: {venue}")
    print(f"Output: {args.output}")
    print(f"Mode: {'Async' if args.use_async else 'Sync'}")
    print("=" * 60)
    print()

    if args.use_async:
        import asyncio
        from src.async_scraper import AsyncAVFMSScraper

        async def run_async():
            async with AsyncAVFMSScraper(
                venue_name=venue,
                output_dir=args.output,
            ) as scraper:
                return await scraper.scrape_all(
                    download=not args.no_download,
                    max_sections=args.max_sections,
                )

        photos = asyncio.run(run_async())
    else:
        from src.scraper import AVFMSScraper

        with AVFMSScraper(
            venue_name=venue,
            output_dir=args.output,
            use_selenium=args.selenium,
        ) as scraper:
            photos = scraper.scrape_all(
                download=not args.no_download,
                max_sections=args.max_sections,
            )

    print()
    print("=" * 60)
    print("Scraping Complete!")
    print("=" * 60)
    print(f"Total photos found: {len(photos)}")
    print(f"Output directory: {args.output}")
    print()
    print("Generated files:")
    print(f"  - {args.output}/metadata.json")
    print(f"  - {args.output}/summary_by_section.json")
    print()
    print("To generate an HTML gallery:")
    print(f"  python -m src.organizer --dir {args.output} --gallery")
    print()
    print("To view statistics:")
    print(f"  python -m src.organizer --dir {args.output} --stats")


if __name__ == "__main__":
    main()
