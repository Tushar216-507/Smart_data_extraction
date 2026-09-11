"""
clean_excel.py
--------------
Reusable post-extraction Excel cleaner.

Reads any extraction Excel file produced by export_to_excel.py,
applies a battery of cleaning rules, and writes a cleaned copy.

Usage:
    python clean_excel.py asu_extraction_data.xlsx
    python clean_excel.py limerick_extraction_data.xlsx --output limerick_clean.xlsx
    python clean_excel.py asu_extraction_data.xlsx --keep-no-url --boilerplate-threshold 20
    python clean_excel.py *.xlsx                    # Clean all at once

Rules applied (in order):
    1. Drop rows with empty Program ID / Field / Value
    2. Drop exact duplicate rows (same program + field + value)
    3. Drop junk fields (ISBNs, book references, internal links, etc.)
    4. Drop boilerplate values (same value appearing in N+ programs)
    5. Drop marketing / CTA / cookie-consent text
    6. Drop rows with no source URL (optional, on by default)
    7. Drop the "other" subcategory junk (references, citations, etc.)
    8. Normalize field names via the canonical field registry

Every dropped row is written to a *_rejected.xlsx audit file so you
can inspect what was removed and tune thresholds.
"""

import argparse
import glob
import re
import sys
from collections import Counter, defaultdict
from copy import copy
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side


# ===================================================================
# CLEANING RULES (tune these lists for your universities)
# ===================================================================

# Fields that are never useful for programme data
JUNK_FIELDS = {
    # Book / citation junk
    "isbn", "author", "publisher", "publication_year", "book_title",
    "book_reference", "citation", "reference", "source",
    "related_topic", "related_topic_url",
    # Internal navigation / link junk
    "link", "url", "course_link", "course_url",
    "tuition_estimator_link", "tuition_estimator_url",
    "intern_name",
    # Generic UI scraping artifacts
    "button_text", "cta_text", "navigation_item",
    "menu_item", "breadcrumb", "footer_text",
    "cookie_notice", "disclaimer",
}

# Fields in the "other" subcategory that are almost always garbage
OTHER_SUBCAT_JUNK_FIELDS = {
    "reference", "definition", "source", "isbn", "author",
    "publisher", "book_title", "citation", "publication_year",
    "book_reference", "related_topic_url", "related_topic",
    "link", "url", "title", "description",
}

# Substrings in VALUE that indicate marketing boilerplate or CTA text
GARBAGE_VALUE_PATTERNS = [
    # CTA / UI junk
    "click here", "learn more", "contact us", "apply now",
    "request info", "subscribe", "sign up", "loading",
    "accept cookies", "cookie policy", "cookie settings",
    "javascript:", "onclick", "btn-",
    # Generic marketing boilerplate (university-agnostic)
    "boost economic prospects for you",
    "have fallen in love",
    "not alone: ",
    "you're not alone",
    "join a chapter near you",
    "have access to the sun devil",
    "schedule a visit",
]

# Regex patterns that indicate a value is a raw URL (not actual content)
URL_ONLY_RE = re.compile(
    r"^https?://[^\s]+$", re.IGNORECASE
)


# ===================================================================
# FIELD CANONICALIZATION (matches schema/field_registry.py)
# ===================================================================

CANONICAL_MAP = {
    "program_name": "programme_name",
    "academic_degree": "degree_type",
    "study_duration": "duration_months",
    "duration": "duration_months",
    "tuition_fee": "tuition_fee_amount",
    "total_course_fee": "tuition_fee_amount",
    "tuition_amount": "tuition_fee_amount",
    "tuition_currency": "tuition_fee_currency",
    "ielts_score": "english_requirement_ielts",
    "toefl_score": "english_requirement_toefl",
    "formal_requirements": "entry_requirements",
    "course_name": "module_name",
    "ects_credits": "module_ects",
    "career_prospects": "career_opportunities",
    "employment_opportunities": "career_opportunities",
    "email": "contact_email",
    "phone": "contact_phone",
}


# ===================================================================
# CORE CLEANER
# ===================================================================

class ExcelCleaner:
    """
    Stateless cleaner that processes one Excel file at a time.
    All thresholds are configurable from the CLI.
    """

    def __init__(
        self,
        boilerplate_threshold: int = 10,
        keep_no_url: bool = False,
        keep_other_subcat: bool = False,
        canonicalize: bool = True,
    ):
        self.boilerplate_threshold = boilerplate_threshold
        self.keep_no_url = keep_no_url
        self.keep_other_subcat = keep_other_subcat
        self.canonicalize = canonicalize

    def clean(self, input_path: Path) -> dict:
        """
        Clean a single Excel file.

        Returns a summary dict with counts.
        """
        print(f"\n{'=' * 70}")
        print(f"  Cleaning: {input_path.name}")
        print(f"{'=' * 70}")

        wb = load_workbook(input_path, read_only=True, data_only=True)

        # Find the data sheet (skip Summary)
        data_sheet = None
        sheet_title = None
        for name in wb.sheetnames:
            if name != "Summary":
                data_sheet = wb[name]
                sheet_title = name
                break

        if data_sheet is None:
            print("  [ERROR] No data sheet found.")
            wb.close()
            return {"status": "error"}

        rows = list(data_sheet.iter_rows(values_only=True))
        wb.close()

        if len(rows) < 2:
            print("  [ERROR] Empty data sheet.")
            return {"status": "error"}

        headers = [str(h).strip() if h else "" for h in rows[0]]
        data_rows = rows[1:]
        original_count = len(data_rows)

        print(f"  Sheet: {sheet_title}")
        print(f"  Original rows: {original_count:,}")

        # -- Parse into dicts -------------------------------------
        col_map = {}
        for i, h in enumerate(headers):
            col_map[h.lower().replace(" ", "_")] = i

        pid_col = col_map.get("program_id", 0)
        pname_col = col_map.get("program_name", 1)
        cat_col = col_map.get("category", 2)
        subcat_col = col_map.get("subcategory", 3)
        field_col = col_map.get("field", 4)
        value_col = col_map.get("value", 5)
        url_col = col_map.get("source_url", 6)
        stype_col = col_map.get("source_type", 7)
        conf_col = col_map.get("confidence", 8)

        def row_to_dict(row):
            def safe(idx):
                return str(row[idx]).strip() if idx < len(row) and row[idx] is not None else ""
            return {
                "program_id": safe(pid_col),
                "program_name": safe(pname_col),
                "category": safe(cat_col),
                "subcategory": safe(subcat_col),
                "field": safe(field_col),
                "value": safe(value_col),
                "source_url": safe(url_col),
                "source_type": safe(stype_col),
                "confidence": safe(conf_col),
            }

        records = [row_to_dict(r) for r in data_rows]

        # -- Cleaning passes --------------------------------------
        clean = records
        rejected = []
        stats = {}

        # Pass 1: Empty essentials
        clean, rej = self._filter(
            clean,
            lambda r: r["program_id"] and r["field"] and r["value"] and r["value"] != "None",
            "empty_essentials",
        )
        rejected.extend(rej)
        stats["empty_essentials"] = len(rej)

        # Pass 2: Exact duplicates (same program + field + value)
        clean, rej = self._dedup(clean)
        rejected.extend(rej)
        stats["duplicates"] = len(rej)

        # Pass 3: Junk fields
        clean, rej = self._filter(
            clean,
            lambda r: r["field"].lower() not in JUNK_FIELDS,
            "junk_field",
        )
        rejected.extend(rej)
        stats["junk_fields"] = len(rej)

        # Pass 4: "other" subcategory junk
        if not self.keep_other_subcat:
            clean, rej = self._filter(
                clean,
                lambda r: not (
                    r["subcategory"].lower() == "other"
                    and r["field"].lower() in OTHER_SUBCAT_JUNK_FIELDS
                ),
                "other_subcat_junk",
            )
            rejected.extend(rej)
            stats["other_subcat_junk"] = len(rej)

        # Pass 5: Boilerplate detection (same value in N+ programs)
        clean, rej = self._remove_boilerplate(clean)
        rejected.extend(rej)
        stats["boilerplate"] = len(rej)

        # Pass 6: Garbage value patterns (marketing, CTA, cookies)
        clean, rej = self._filter(
            clean,
            lambda r: not self._is_garbage_value(r["value"]),
            "garbage_value",
        )
        rejected.extend(rej)
        stats["garbage_values"] = len(rej)

        # Pass 7: URL-only values (value is just a raw URL)
        clean, rej = self._filter(
            clean,
            lambda r: not URL_ONLY_RE.match(r["value"]),
            "url_only_value",
        )
        rejected.extend(rej)
        stats["url_only_values"] = len(rej)

        # Pass 8: No source URL
        if not self.keep_no_url:
            clean, rej = self._filter(
                clean,
                lambda r: r["source_url"] and r["source_url"] != "None",
                "no_source_url",
            )
            rejected.extend(rej)
            stats["no_source_url"] = len(rej)

        # Pass 9: Canonicalize field names
        if self.canonicalize:
            for r in clean:
                canonical = CANONICAL_MAP.get(r["field"].lower())
                if canonical:
                    r["field"] = canonical

        # -- Write outputs ----------------------------------------
        stem = input_path.stem
        suffix = input_path.suffix
        parent = input_path.parent

        clean_path = parent / f"{stem}_clean{suffix}"
        rejected_path = parent / f"{stem}_rejected{suffix}"

        uni_name = sheet_title.replace(" - All Facts", "").strip() if sheet_title else stem

        self._write_excel(clean, clean_path, uni_name, is_rejected=False)
        self._write_excel(rejected, rejected_path, uni_name, is_rejected=True)

        # -- Print report -----------------------------------------
        total_removed = original_count - len(clean)
        pct = 100 * total_removed / max(original_count, 1)

        clean_programs = len(set(r["program_id"] for r in clean))
        orig_programs = len(set(r["program_id"] for r in records))

        print(f"\n  -- Cleaning Report ------------------------------")
        print(f"  Original rows:       {original_count:>10,}")
        print(f"  Clean rows:          {len(clean):>10,}")
        print(f"  Removed:             {total_removed:>10,}  ({pct:.1f}%)")
        print(f"  Original programs:   {orig_programs:>10,}")
        print(f"  Clean programs:      {clean_programs:>10,}")
        print(f"")
        print(f"  Breakdown of removed rows:")
        for reason, count in sorted(stats.items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"    {reason:25s} {count:>8,}")
        print(f"")
        print(f"  Clean file:    {clean_path}")
        print(f"  Rejected file: {rejected_path}")

        return {
            "status": "ok",
            "input": str(input_path),
            "original_rows": original_count,
            "clean_rows": len(clean),
            "removed_rows": total_removed,
            "removed_pct": round(pct, 1),
            "original_programs": orig_programs,
            "clean_programs": clean_programs,
            "breakdown": stats,
        }

    # --------------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------------

    @staticmethod
    def _filter(records, predicate, reason):
        """Split records into (pass, fail) based on predicate."""
        passed, failed = [], []
        for r in records:
            if predicate(r):
                passed.append(r)
            else:
                r["_reject_reason"] = reason
                failed.append(r)
        return passed, failed

    @staticmethod
    def _dedup(records):
        """Remove exact duplicates (same program_id + field + value)."""
        seen = set()
        unique, dupes = [], []
        for r in records:
            key = (r["program_id"], r["field"].lower(), r["value"][:200].lower())
            if key in seen:
                r["_reject_reason"] = "duplicate"
                dupes.append(r)
            else:
                seen.add(key)
                unique.append(r)
        return unique, dupes

    def _remove_boilerplate(self, records):
        """Remove values that appear across N+ distinct programs."""
        # Build value → set of program_ids (only for substantial values)
        value_programs = defaultdict(set)
        for r in records:
            val = r["value"].strip()
            if len(val) > 20:  # Only check substantial text
                value_programs[val[:150].lower()].add(r["program_id"])

        # Identify boilerplate values
        boilerplate_vals = {
            val
            for val, pids in value_programs.items()
            if len(pids) >= self.boilerplate_threshold
        }

        passed, failed = [], []
        for r in records:
            val_key = r["value"][:150].lower().strip()
            if len(r["value"].strip()) > 20 and val_key in boilerplate_vals:
                r["_reject_reason"] = "boilerplate"
                failed.append(r)
            else:
                passed.append(r)
        return passed, failed

    @staticmethod
    def _is_garbage_value(value: str) -> bool:
        """Check if a value matches known garbage patterns."""
        lower = value.lower()
        return any(pat in lower for pat in GARBAGE_VALUE_PATTERNS)

    @staticmethod
    def _write_excel(records, path, uni_name, is_rejected=False):
        """Write records to an Excel file with styling."""
        wb = Workbook()
        ws = wb.active
        ws.title = f"{uni_name} - {'Rejected' if is_rejected else 'Clean'}"

        headers = [
            "Program ID", "Program Name", "Category", "Subcategory",
            "Field", "Value", "Source URL", "Source Type", "Confidence",
        ]
        if is_rejected:
            headers.append("Reject Reason")

        # Styling
        header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
        header_fill = PatternFill(
            start_color="2E7D32" if not is_rejected else "C62828",
            end_color="2E7D32" if not is_rejected else "C62828",
            fill_type="solid",
        )
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin_border = Border(
            left=Side(style="thin", color="D9D9D9"),
            right=Side(style="thin", color="D9D9D9"),
            top=Side(style="thin", color="D9D9D9"),
            bottom=Side(style="thin", color="D9D9D9"),
        )
        even_fill = PatternFill(start_color="F1F8E9" if not is_rejected else "FFEBEE", end_color="F1F8E9" if not is_rejected else "FFEBEE", fill_type="solid")
        odd_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            cell.border = thin_border

        data_font = Font(name="Calibri", size=10)
        wrap_align = Alignment(vertical="top", wrap_text=True)

        for row_idx, r in enumerate(records, start=2):
            fill = even_fill if row_idx % 2 == 0 else odd_fill
            values = [
                r["program_id"], r["program_name"], r["category"],
                r["subcategory"], r["field"], r["value"],
                r["source_url"], r["source_type"], r["confidence"],
            ]
            if is_rejected:
                values.append(r.get("_reject_reason", ""))

            for col_idx, val in enumerate(values, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.fill = fill
                cell.border = thin_border
                cell.alignment = wrap_align

        # Column widths
        col_widths = [12, 45, 14, 18, 30, 60, 50, 14, 12]
        if is_rejected:
            col_widths.append(20)
        for i, w in enumerate(col_widths, start=1):
            from openpyxl.utils import get_column_letter
            ws.column_dimensions[get_column_letter(i)].width = w

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(records) + 1}"

        # Summary sheet
        ws_sum = wb.create_sheet(title="Summary", index=0)
        programs = set(r["program_id"] for r in records)
        subcats = Counter(r["subcategory"] for r in records)

        title_font = Font(name="Calibri", bold=True, size=14, color="2E7D32" if not is_rejected else "C62828")
        label_font = Font(name="Calibri", bold=True, size=11)
        value_font = Font(name="Calibri", size=11)

        ws_sum.column_dimensions["A"].width = 35
        ws_sum.column_dimensions["B"].width = 20

        tag = "Clean" if not is_rejected else "Rejected"
        ws_sum.cell(row=1, column=1, value=f"{uni_name} -- {tag} Summary").font = title_font
        ws_sum.merge_cells("A1:B1")

        summary = [
            ("University", uni_name),
            ("Total Programs", len(programs)),
            ("Total Facts", len(records)),
            ("", ""),
            ("Subcategory Breakdown", "Count"),
        ]
        for s in sorted(subcats.keys()):
            summary.append((s, subcats[s]))

        if is_rejected:
            summary.append(("", ""))
            summary.append(("Rejection Reasons", "Count"))
            reasons = Counter(r.get("_reject_reason", "") for r in records)
            for reason, count in reasons.most_common():
                summary.append((reason, count))

        for row_idx, (label, value) in enumerate(summary, start=3):
            cell_a = ws_sum.cell(row=row_idx, column=1, value=label)
            cell_b = ws_sum.cell(row=row_idx, column=2, value=value)
            if label in ("Subcategory Breakdown", "University", "Total Programs", "Total Facts", "Rejection Reasons"):
                cell_a.font = label_font
                cell_b.font = label_font
            else:
                cell_a.font = value_font
                cell_b.font = value_font

        wb.save(path)


# ===================================================================
# CLI
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Clean garbage data from extraction Excel files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python clean_excel.py asu_extraction_data.xlsx
  python clean_excel.py *.xlsx
  python clean_excel.py asu_extraction_data.xlsx --keep-no-url
  python clean_excel.py asu_extraction_data.xlsx --boilerplate-threshold 20
""",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Excel file(s) to clean. Supports glob patterns.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (only works with a single input file).",
    )
    parser.add_argument(
        "--boilerplate-threshold",
        type=int,
        default=10,
        help="Drop values appearing in this many programs or more (default: 10).",
    )
    parser.add_argument(
        "--keep-no-url",
        action="store_true",
        help="Keep rows that have no source URL (dropped by default).",
    )
    parser.add_argument(
        "--keep-other-subcat",
        action="store_true",
        help="Keep junk fields in the 'other' subcategory (dropped by default).",
    )
    parser.add_argument(
        "--no-canonicalize",
        action="store_true",
        help="Skip field name canonicalization.",
    )

    args = parser.parse_args()

    # Expand glob patterns
    all_files = []
    for pattern in args.files:
        matched = glob.glob(pattern)
        if not matched:
            print(f"  [WARN] No files matched: {pattern}")
        all_files.extend(matched)

    if not all_files:
        print("  [ERROR] No input files found.")
        sys.exit(1)

    cleaner = ExcelCleaner(
        boilerplate_threshold=args.boilerplate_threshold,
        keep_no_url=args.keep_no_url,
        keep_other_subcat=args.keep_other_subcat,
        canonicalize=not args.no_canonicalize,
    )

    results = []
    for filepath in all_files:
        path = Path(filepath)
        if not path.exists():
            print(f"  [SKIP] {filepath} not found")
            continue
        if "_clean" in path.stem or "_rejected" in path.stem:
            print(f"  [SKIP] {filepath} (already a cleaned/rejected file)")
            continue

        result = cleaner.clean(path)
        results.append(result)

    # Final summary
    if len(results) > 1:
        print(f"\n{'=' * 70}")
        print(f"  BATCH SUMMARY")
        print(f"{'=' * 70}")
        for r in results:
            if r["status"] == "ok":
                print(
                    f"  {Path(r['input']).name:40s}  "
                    f"{r['original_rows']:>8,} -> {r['clean_rows']:>8,}  "
                    f"(-{r['removed_pct']}%)"
                )


if __name__ == "__main__":
    main()
