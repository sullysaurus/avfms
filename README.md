# A View From My Seat - MSG Photo Scraper

Scrapes all photos from Madison Square Garden on [aviewfrommyseat.com](https://aviewfrommyseat.com/venue/Madison+Square+Garden/) and organizes them by **section**, **row**, and **seat**.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Scrape Madison Square Garden photos
python scrape_msg.py

# Or use async mode for faster downloads
python scrape_msg.py --async

# Test with just 5 sections first
python scrape_msg.py --max-sections 5
```

## Output Structure

Photos are organized in the following directory structure:

```
output/msg/
├── section_101/
│   ├── row_A/
│   │   ├── section_101_row_A_seat_1_12345.jpg
│   │   └── section_101_row_A_seat_2_12346.jpg
│   └── row_B/
│       └── section_101_row_B_12347.jpg
├── section_102/
│   └── ...
├── metadata.json          # Full photo data
├── summary_by_section.json # Organized index
└── gallery.html           # HTML viewer (generated)
```

## Commands

### Scrape Photos

```bash
# Basic scrape (all sections)
python scrape_msg.py

# Async mode (faster, concurrent downloads)
python scrape_msg.py --async

# Limit sections for testing
python scrape_msg.py --max-sections 10

# Metadata only (no image downloads)
python scrape_msg.py --no-download

# Use Selenium browser (slower but handles anti-bot)
python scrape_msg.py --selenium
```

### Organize & View

```bash
# View statistics
python -m src.organizer --dir output/msg --stats

# See photo tree structure
python -m src.organizer --dir output/msg --tree

# Generate HTML gallery
python -m src.organizer --dir output/msg --gallery

# Export to CSV
python -m src.organizer --dir output/msg --csv

# Search by section
python -m src.cli search --section 101 --row A
```

## CLI Usage

```bash
# Full CLI
python -m src.cli scrape --venue "Madison+Square+Garden" --output output/msg
python -m src.cli organize --stats
python -m src.cli search --section 109 --row 6
python -m src.cli sections
```

## API

```python
from src.scraper import AVFMSScraper

with AVFMSScraper(
    venue_name="Madison+Square+Garden",
    output_dir="output/msg",
) as scraper:
    # Get all sections
    sections = scraper.get_sections()

    # Scrape all photos
    photos = scraper.scrape_all(download=True)

    # Access organized data
    for photo in photos:
        print(f"Section {photo.section}, Row {photo.row}, Seat {photo.seat}")
        print(f"  Image: {photo.image_url}")
```

### Async API (faster)

```python
import asyncio
from src.async_scraper import AsyncAVFMSScraper

async def main():
    async with AsyncAVFMSScraper(
        venue_name="Madison+Square+Garden",
        output_dir="output/msg",
        max_concurrent=10,  # Concurrent downloads
    ) as scraper:
        photos = await scraper.scrape_all()
        print(f"Scraped {len(photos)} photos")

asyncio.run(main())
```

## Output Files

| File | Description |
|------|-------------|
| `metadata.json` | Complete photo metadata (ID, section, row, seat, URLs) |
| `summary_by_section.json` | Photos organized by section → row |
| `gallery.html` | Interactive HTML photo gallery |
| `photos.csv` | Spreadsheet export |

## Requirements

- Python 3.9+
- For Selenium mode: Chrome/Chromium browser

## Notes

- The scraper includes rate limiting (1-3 second delays) to be respectful
- If you get 403 errors, use `--selenium` mode
- Photos are deduplicated by photo ID
- Existing photos are skipped on re-runs

## Data Source

Photos from [A View From My Seat](https://aviewfrommyseat.com/venue/Madison+Square+Garden/) - a user-contributed database of seat views.
