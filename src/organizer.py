"""
Photo Organizer Module

Organizes and manages scraped photos by section, row, and seat.
"""

import json
import shutil
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SeatLocation:
    """Represents a seat location in the venue."""
    section: str
    row: Optional[str]
    seat: Optional[str]

    def __str__(self) -> str:
        parts = [f"Section {self.section}"]
        if self.row:
            parts.append(f"Row {self.row}")
        if self.seat:
            parts.append(f"Seat {self.seat}")
        return ", ".join(parts)

    def to_path(self) -> str:
        """Convert to a file path-safe string."""
        parts = [f"section_{self.section}"]
        if self.row:
            parts.append(f"row_{self.row}")
        if self.seat:
            parts.append(f"seat_{self.seat}")
        return "/".join(parts)


class PhotoOrganizer:
    """Organizes and manages scraped photos."""

    def __init__(self, base_dir: str = "output"):
        self.base_dir = Path(base_dir)
        self.metadata_file = self.base_dir / "metadata.json"
        self.summary_file = self.base_dir / "summary_by_section.json"
        self._metadata = None
        self._summary = None

    def load_metadata(self) -> dict:
        """Load the metadata file."""
        if self._metadata is None:
            if self.metadata_file.exists():
                with open(self.metadata_file) as f:
                    self._metadata = json.load(f)
            else:
                self._metadata = {"venue": "", "photos": [], "total_photos": 0, "sections": 0}
        return self._metadata

    def load_summary(self) -> dict:
        """Load the summary file."""
        if self._summary is None:
            if self.summary_file.exists():
                with open(self.summary_file) as f:
                    self._summary = json.load(f)
            else:
                self._summary = {}
        return self._summary

    def get_statistics(self) -> dict:
        """Get statistics about the scraped photos."""
        metadata = self.load_metadata()

        photos = metadata.get("photos", [])
        sections = set()
        rows_by_section = defaultdict(set)
        seats_by_section_row = defaultdict(set)

        for photo in photos:
            section = photo.get("section", "unknown")
            row = photo.get("row")
            seat = photo.get("seat")

            sections.add(section)
            if row:
                rows_by_section[section].add(row)
            if seat:
                seats_by_section_row[f"{section}_{row}"].add(seat)

        return {
            "venue": metadata.get("venue", "Unknown"),
            "total_photos": len(photos),
            "total_sections": len(sections),
            "sections": sorted(sections),
            "rows_per_section": {s: len(rows) for s, rows in rows_by_section.items()},
            "coverage": {
                "sections_with_photos": len(sections),
                "total_rows": sum(len(rows) for rows in rows_by_section.values()),
                "total_unique_seats": sum(len(seats) for seats in seats_by_section_row.values()),
            },
        }

    def list_sections(self) -> list[str]:
        """List all sections that have photos."""
        summary = self.load_summary()
        return sorted(summary.keys())

    def list_rows_in_section(self, section: str) -> list[str]:
        """List all rows in a section."""
        summary = self.load_summary()
        if section in summary:
            return sorted(summary[section].get("rows", {}).keys())
        return []

    def list_photos_in_row(self, section: str, row: str) -> list[dict]:
        """List all photos in a specific row."""
        summary = self.load_summary()
        if section in summary:
            rows = summary[section].get("rows", {})
            if row in rows:
                return rows[row]
        return []

    def get_photos_by_location(
        self,
        section: Optional[str] = None,
        row: Optional[str] = None,
        seat: Optional[str] = None,
    ) -> list[dict]:
        """Get photos filtered by location criteria."""
        metadata = self.load_metadata()
        photos = metadata.get("photos", [])

        results = []
        for photo in photos:
            if section and photo.get("section") != section:
                continue
            if row and photo.get("row") != row:
                continue
            if seat and photo.get("seat") != seat:
                continue
            results.append(photo)

        return results

    def get_photo_files(self, section: Optional[str] = None) -> list[Path]:
        """Get all photo files, optionally filtered by section."""
        photos = []

        if section:
            section_dir = self.base_dir / f"section_{section}"
            if section_dir.exists():
                photos.extend(section_dir.rglob("*.jpg"))
                photos.extend(section_dir.rglob("*.jpeg"))
                photos.extend(section_dir.rglob("*.png"))
                photos.extend(section_dir.rglob("*.gif"))
        else:
            for section_dir in self.base_dir.glob("section_*"):
                photos.extend(section_dir.rglob("*.jpg"))
                photos.extend(section_dir.rglob("*.jpeg"))
                photos.extend(section_dir.rglob("*.png"))
                photos.extend(section_dir.rglob("*.gif"))

        return sorted(photos)

    def reorganize_flat(self, output_dir: str = "output_flat") -> int:
        """Reorganize photos into a flat structure with descriptive names."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        metadata = self.load_metadata()
        photos = metadata.get("photos", [])

        count = 0
        for photo in photos:
            section = photo.get("section", "unknown")
            row = photo.get("row", "unknown")
            seat = photo.get("seat", "")
            photo_id = photo.get("photo_id", "")

            # Find the actual file
            pattern = f"*{photo_id}*"
            files = list(self.base_dir.rglob(pattern))

            if files:
                source = files[0]
                ext = source.suffix

                if seat:
                    new_name = f"section{section}_row{row}_seat{seat}_{photo_id}{ext}"
                else:
                    new_name = f"section{section}_row{row}_{photo_id}{ext}"

                dest = output_path / new_name
                shutil.copy2(source, dest)
                count += 1

        logger.info(f"Reorganized {count} photos to {output_dir}")
        return count

    def generate_html_gallery(self, output_file: str = "gallery.html") -> str:
        """Generate an HTML gallery of all photos."""
        metadata = self.load_metadata()
        venue = metadata.get("venue", "Venue")
        photos = metadata.get("photos", [])

        # Group by section
        by_section = defaultdict(list)
        for photo in photos:
            section = photo.get("section", "unknown")
            by_section[section].append(photo)

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>{venue} - Photo Gallery</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }",
            "h1 { color: #4a9eff; }",
            "h2 { color: #ffa64a; border-bottom: 1px solid #333; padding-bottom: 10px; }",
            ".section { margin-bottom: 40px; }",
            ".photo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }",
            ".photo-card { background: #2a2a2a; border-radius: 8px; overflow: hidden; }",
            ".photo-card img { width: 100%; height: 200px; object-fit: cover; }",
            ".photo-info { padding: 10px; }",
            ".photo-info p { margin: 5px 0; font-size: 14px; }",
            ".stats { background: #2a2a2a; padding: 20px; border-radius: 8px; margin-bottom: 30px; }",
            ".stats span { margin-right: 30px; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{venue} - Photo Gallery</h1>",
            "<div class='stats'>",
            f"<span><strong>Total Photos:</strong> {len(photos)}</span>",
            f"<span><strong>Sections:</strong> {len(by_section)}</span>",
            "</div>",
        ]

        for section in sorted(by_section.keys()):
            section_photos = by_section[section]
            html_parts.append(f"<div class='section' id='section-{section}'>")
            html_parts.append(f"<h2>Section {section} ({len(section_photos)} photos)</h2>")
            html_parts.append("<div class='photo-grid'>")

            for photo in section_photos:
                row = photo.get("row", "?")
                seat = photo.get("seat", "?")
                img_url = photo.get("image_url", "")
                page_url = photo.get("page_url", "#")

                html_parts.append("<div class='photo-card'>")
                html_parts.append(f"<a href='{page_url}' target='_blank'>")
                html_parts.append(f"<img src='{img_url}' alt='Section {section}, Row {row}' loading='lazy'>")
                html_parts.append("</a>")
                html_parts.append("<div class='photo-info'>")
                html_parts.append(f"<p><strong>Row:</strong> {row}</p>")
                if seat:
                    html_parts.append(f"<p><strong>Seat:</strong> {seat}</p>")
                html_parts.append("</div>")
                html_parts.append("</div>")

            html_parts.append("</div>")
            html_parts.append("</div>")

        html_parts.extend([
            "</body>",
            "</html>",
        ])

        output_path = self.base_dir / output_file
        with open(output_path, "w") as f:
            f.write("\n".join(html_parts))

        logger.info(f"Generated HTML gallery: {output_path}")
        return str(output_path)

    def export_csv(self, output_file: str = "photos.csv") -> str:
        """Export photo data to CSV."""
        import csv

        metadata = self.load_metadata()
        photos = metadata.get("photos", [])

        output_path = self.base_dir / output_file
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["photo_id", "section", "row", "seat", "image_url", "page_url", "event", "contributor"])

            for photo in photos:
                writer.writerow([
                    photo.get("photo_id", ""),
                    photo.get("section", ""),
                    photo.get("row", ""),
                    photo.get("seat", ""),
                    photo.get("image_url", ""),
                    photo.get("page_url", ""),
                    photo.get("event", ""),
                    photo.get("contributor", ""),
                ])

        logger.info(f"Exported {len(photos)} photos to {output_path}")
        return str(output_path)

    def print_tree(self):
        """Print a tree view of the organized photos."""
        summary = self.load_summary()

        print(f"\nPhoto Organization Tree")
        print("=" * 50)

        for section in sorted(summary.keys()):
            rows = summary[section].get("rows", {})
            photo_count = sum(len(photos) for photos in rows.values())
            print(f"\n[Section {section}] ({photo_count} photos)")

            for row in sorted(rows.keys()):
                photos = rows[row]
                seats = [p.get("seat") for p in photos if p.get("seat")]
                seat_info = f", seats: {', '.join(sorted(set(seats)))}" if seats else ""
                print(f"  ├── Row {row}: {len(photos)} photos{seat_info}")


def main():
    """CLI for the photo organizer."""
    import argparse

    parser = argparse.ArgumentParser(description="Organize and manage scraped photos")
    parser.add_argument("--dir", default="output", help="Base directory with scraped photos")
    parser.add_argument("--stats", action="store_true", help="Show statistics")
    parser.add_argument("--tree", action="store_true", help="Show photo tree")
    parser.add_argument("--gallery", action="store_true", help="Generate HTML gallery")
    parser.add_argument("--csv", action="store_true", help="Export to CSV")
    parser.add_argument("--flat", action="store_true", help="Create flat directory structure")
    parser.add_argument("--section", help="Filter by section")
    parser.add_argument("--row", help="Filter by row")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    organizer = PhotoOrganizer(args.dir)

    if args.stats:
        stats = organizer.get_statistics()
        print(f"\nVenue: {stats['venue']}")
        print(f"Total Photos: {stats['total_photos']}")
        print(f"Total Sections: {stats['total_sections']}")
        print(f"Sections: {', '.join(stats['sections'][:20])}...")
        print(f"\nCoverage:")
        for key, value in stats['coverage'].items():
            print(f"  {key}: {value}")

    if args.tree:
        organizer.print_tree()

    if args.gallery:
        path = organizer.generate_html_gallery()
        print(f"Gallery generated: {path}")

    if args.csv:
        path = organizer.export_csv()
        print(f"CSV exported: {path}")

    if args.flat:
        count = organizer.reorganize_flat()
        print(f"Reorganized {count} photos")

    if args.section:
        photos = organizer.get_photos_by_location(
            section=args.section,
            row=args.row,
        )
        print(f"\nFound {len(photos)} photos:")
        for p in photos[:10]:
            print(f"  Section {p['section']}, Row {p.get('row', '?')}, Seat {p.get('seat', '?')}")
        if len(photos) > 10:
            print(f"  ... and {len(photos) - 10} more")


if __name__ == "__main__":
    main()
