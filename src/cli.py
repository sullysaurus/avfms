#!/usr/bin/env python3
"""
A View From My Seat - CLI

Command-line interface for scraping and organizing venue photos.
"""

import sys
import logging
import argparse
from pathlib import Path

from .scraper import AVFMSScraper
from .organizer import PhotoOrganizer


def setup_logging(verbose: bool = False, log_file: str = None):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers,
    )


def cmd_scrape(args):
    """Run the scraper."""
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger(__name__)

    logger.info(f"Starting scrape for venue: {args.venue}")

    with AVFMSScraper(
        venue_name=args.venue,
        output_dir=args.output,
        delay_range=(args.min_delay, args.max_delay),
        use_selenium=args.selenium,
    ) as scraper:
        photos = scraper.scrape_all(
            download=not args.no_download,
            max_sections=args.max_sections,
        )

    print(f"\n{'='*50}")
    print(f"Scraping Complete!")
    print(f"{'='*50}")
    print(f"Venue: {args.venue}")
    print(f"Total photos found: {len(photos)}")
    print(f"Output directory: {args.output}")
    print(f"\nFiles created:")
    print(f"  - metadata.json: Full photo metadata")
    print(f"  - summary_by_section.json: Organized by section/row")
    print(f"\nRun 'avfms organize --help' to see organization options")


def cmd_organize(args):
    """Organize scraped photos."""
    setup_logging(args.verbose)
    organizer = PhotoOrganizer(args.dir)

    if args.stats:
        stats = organizer.get_statistics()
        print(f"\n{'='*50}")
        print(f"Photo Statistics")
        print(f"{'='*50}")
        print(f"Venue: {stats['venue']}")
        print(f"Total Photos: {stats['total_photos']}")
        print(f"Total Sections: {stats['total_sections']}")
        if stats['sections']:
            sections_display = ', '.join(stats['sections'][:15])
            if len(stats['sections']) > 15:
                sections_display += f" ... (+{len(stats['sections']) - 15} more)"
            print(f"Sections: {sections_display}")
        print(f"\nCoverage:")
        for key, value in stats['coverage'].items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        return

    if args.tree:
        organizer.print_tree()
        return

    if args.gallery:
        path = organizer.generate_html_gallery()
        print(f"HTML gallery generated: {path}")
        return

    if args.csv:
        path = organizer.export_csv()
        print(f"CSV exported: {path}")
        return

    if args.flat:
        count = organizer.reorganize_flat(args.flat_output)
        print(f"Reorganized {count} photos to flat structure")
        return

    # Default: show stats
    stats = organizer.get_statistics()
    print(f"Found {stats['total_photos']} photos in {stats['total_sections']} sections")
    print("Use --help to see organization options")


def cmd_search(args):
    """Search for photos by location."""
    setup_logging(args.verbose)
    organizer = PhotoOrganizer(args.dir)

    photos = organizer.get_photos_by_location(
        section=args.section,
        row=args.row,
        seat=args.seat,
    )

    if not photos:
        print("No photos found matching criteria")
        return

    print(f"\nFound {len(photos)} photos:")
    print("-" * 60)

    for i, photo in enumerate(photos[:args.limit]):
        section = photo.get('section', '?')
        row = photo.get('row', '?')
        seat = photo.get('seat', '-')
        photo_id = photo.get('photo_id', '?')
        url = photo.get('page_url', '')

        print(f"{i+1}. Section {section}, Row {row}, Seat {seat}")
        print(f"   ID: {photo_id}")
        print(f"   URL: {url}")
        print()

    if len(photos) > args.limit:
        print(f"... and {len(photos) - args.limit} more (use --limit to show more)")


def cmd_sections(args):
    """List all sections."""
    setup_logging(args.verbose)
    organizer = PhotoOrganizer(args.dir)

    sections = organizer.list_sections()

    if not sections:
        print("No sections found. Have you run the scraper?")
        return

    print(f"\nSections with photos ({len(sections)} total):")
    print("-" * 40)

    for section in sections:
        rows = organizer.list_rows_in_section(section)
        photos = organizer.get_photos_by_location(section=section)
        print(f"  Section {section}: {len(rows)} rows, {len(photos)} photos")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="avfms",
        description="A View From My Seat - Photo Scraper & Organizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all Madison Square Garden photos
  avfms scrape

  # Scrape with custom venue and output
  avfms scrape --venue "Yankee+Stadium" --output yankee_photos

  # Scrape only first 5 sections (for testing)
  avfms scrape --max-sections 5

  # View statistics
  avfms organize --stats

  # Generate HTML gallery
  avfms organize --gallery

  # Search for specific section
  avfms search --section 101 --row A

  # List all sections
  avfms sections
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape photos from venue")
    scrape_parser.add_argument(
        "--venue",
        default="Madison+Square+Garden",
        help="Venue name (URL-encoded, default: Madison+Square+Garden)",
    )
    scrape_parser.add_argument(
        "--output", "-o",
        default="output",
        help="Output directory (default: output)",
    )
    scrape_parser.add_argument(
        "--max-sections",
        type=int,
        help="Maximum sections to scrape (for testing)",
    )
    scrape_parser.add_argument(
        "--no-download",
        action="store_true",
        help="Only collect metadata, don't download images",
    )
    scrape_parser.add_argument(
        "--selenium",
        action="store_true",
        help="Use Selenium for browser automation",
    )
    scrape_parser.add_argument(
        "--min-delay",
        type=float,
        default=1.0,
        help="Minimum delay between requests (default: 1.0s)",
    )
    scrape_parser.add_argument(
        "--max-delay",
        type=float,
        default=3.0,
        help="Maximum delay between requests (default: 3.0s)",
    )
    scrape_parser.add_argument(
        "--log-file",
        help="Write logs to file",
    )
    scrape_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    scrape_parser.set_defaults(func=cmd_scrape)

    # Organize command
    organize_parser = subparsers.add_parser("organize", help="Organize scraped photos")
    organize_parser.add_argument(
        "--dir", "-d",
        default="output",
        help="Directory with scraped photos (default: output)",
    )
    organize_parser.add_argument(
        "--stats",
        action="store_true",
        help="Show photo statistics",
    )
    organize_parser.add_argument(
        "--tree",
        action="store_true",
        help="Show photo organization tree",
    )
    organize_parser.add_argument(
        "--gallery",
        action="store_true",
        help="Generate HTML gallery",
    )
    organize_parser.add_argument(
        "--csv",
        action="store_true",
        help="Export to CSV file",
    )
    organize_parser.add_argument(
        "--flat",
        action="store_true",
        help="Create flat directory structure",
    )
    organize_parser.add_argument(
        "--flat-output",
        default="output_flat",
        help="Output directory for flat structure",
    )
    organize_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    organize_parser.set_defaults(func=cmd_organize)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for photos")
    search_parser.add_argument(
        "--dir", "-d",
        default="output",
        help="Directory with scraped photos (default: output)",
    )
    search_parser.add_argument(
        "--section", "-s",
        help="Filter by section",
    )
    search_parser.add_argument(
        "--row", "-r",
        help="Filter by row",
    )
    search_parser.add_argument(
        "--seat",
        help="Filter by seat",
    )
    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum results to show (default: 20)",
    )
    search_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    search_parser.set_defaults(func=cmd_search)

    # Sections command
    sections_parser = subparsers.add_parser("sections", help="List all sections")
    sections_parser.add_argument(
        "--dir", "-d",
        default="output",
        help="Directory with scraped photos (default: output)",
    )
    sections_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    sections_parser.set_defaults(func=cmd_sections)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
