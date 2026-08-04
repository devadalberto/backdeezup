"""
Audit management command to map UNADJUSTEDNONRAW duplicate image groups.

Identifies Google Photos auto-generated variants of the same photo:
- UNADJUSTEDNONRAW_mini_1d6.jpg
- UNADJUSTEDNONRAW_thumb_1d6.jpg
- UNADJUSTEDNONRAW_largepv_1b2.jpg

The hex suffix (1d6, 1b2) is the asset ID shared across variants.
Types: mini, thumb, largepv (+ any full-res original with that asset ID).

Usage:
    python manage.py audit_duplicates
    python manage.py audit_duplicates --output /tmp/my_report.csv

Output: CSV report with columns:
    hex_id, variant_type, image_id, title, imported_at, keep

NO DELETIONS in this phase -- audit only.
"""
import csv
import os
import re
from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q

from media_vault.models import VaultImage


class Command(BaseCommand):
    help = "Audit UNADJUSTEDNONRAW duplicate image groups in the vault"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Path to CSV output file (default: /app/media/reports/duplicate_audit_YYYY-MM-DD.csv)",
        )

    def handle(self, *args, **options):
        output_path = options.get("output")

        # If no output path specified, use default
        if not output_path:
            report_dir = "/app/media/reports"
            os.makedirs(report_dir, exist_ok=True)
            today = datetime.now().strftime("%Y-%m-%d")
            output_path = os.path.join(report_dir, f"duplicate_audit_{today}.csv")

        # Query all VaultImage records with UNADJUSTEDNONRAW pattern
        unadjusted_images = VaultImage.objects.filter(
            title__startswith="UNADJUSTEDNONRAW"
        ).order_by("title")

        self.stdout.write(f"Found {unadjusted_images.count()} UNADJUSTEDNONRAW images")

        # Group by hex asset ID suffix
        # Pattern: UNADJUSTEDNONRAW_<variant_type>_<hex_id>.jpg
        groups = defaultdict(lambda: defaultdict(list))

        variant_pattern = re.compile(
            r"^UNADJUSTEDNONRAW_(?P<variant_type>\w+)_(?P<hex_id>[a-f0-9]+)\.jpg$",
            re.IGNORECASE,
        )

        for img in unadjusted_images:
            title = img.title
            match = variant_pattern.match(title)

            if match:
                hex_id = match.group("hex_id").lower()
                variant_type = match.group("variant_type").lower()
                groups[hex_id][variant_type].append(img)
            else:
                # Title doesn't match variant pattern; might be a full-res original
                # with that asset ID (e.g., just "UNADJUSTEDNONRAW_<hex_id>.jpg")
                # or some other UNADJUSTEDNONRAW naming.
                # Try to extract hex ID from the end
                match_alt = re.search(r"(?P<hex_id>[a-f0-9]+)\.jpg$", title, re.IGNORECASE)
                if match_alt:
                    hex_id = match_alt.group("hex_id").lower()
                    groups[hex_id]["original"].append(img)

        self.stdout.write(f"Grouped into {len(groups)} unique asset ID groups")

        # Prepare rows for CSV
        rows = []
        total_deletable = 0

        for hex_id in sorted(groups.keys()):
            group = groups[hex_id]

            # Check if this group has an original (not just variants)
            has_original = "original" in group

            for variant_type in sorted(group.keys()):
                for img in group[variant_type]:
                    # Keep original images; mark variants as deletable only if an original exists
                    # If no original exists, keep all variants (they're the best we have)
                    if variant_type == "original":
                        keep = True
                    else:
                        # It's a variant (mini/thumb/largepv)
                        keep = not has_original  # Keep if NO original exists

                    if not keep:
                        total_deletable += 1

                    rows.append(
                        {
                            "hex_id": hex_id,
                            "variant_type": variant_type,
                            "image_id": img.id,
                            "title": img.title,
                            "imported_at": img.imported_at.isoformat() if img.imported_at else "",
                            "keep": keep,
                        }
                    )

        # Write CSV
        csv_columns = ["hex_id", "variant_type", "image_id", "title", "imported_at", "keep"]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"\nCSV report written to: {output_path}"))

        # Summary statistics
        groups_with_originals = sum(1 for g in groups.values() if "original" in g)
        groups_without_originals = len(groups) - groups_with_originals

        summary = (
            f"\n=== AUDIT SUMMARY ===\n"
            f"Total duplicate groups: {len(groups)}\n"
            f"Groups with original: {groups_with_originals}\n"
            f"Groups without original (variants only): {groups_without_originals}\n"
            f"Total images that could be deleted: {total_deletable}\n"
            f"Total images in vault (UNADJUSTEDNONRAW): {unadjusted_images.count()}"
        )

        self.stdout.write(self.style.SUCCESS(summary))
