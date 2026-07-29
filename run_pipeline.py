"""
run_pipeline.py

Single entry point for the university data extraction pipeline.

Usage:

    python run_pipeline.py --university "https://www.lmu.de/en/"

    python run_pipeline.py --university "https://www.mit.edu/" --programs 1

    python run_pipeline.py --university "https://www.lmu.de/en/" --programs 5 --continue-on-error

This file is only a CLI wrapper. All orchestration logic lives
in pipelines/university_pipeline.py (UniversityPipeline).
"""

import sys
import argparse
from urllib.parse import urlparse
import traceback

from pipelines.university_pipeline import UniversityPipeline


# ==============================================================
# CLI
# ==============================================================

def parse_args():
    """Parse and return command-line arguments."""

    parser = argparse.ArgumentParser(
        description="University Data Extraction Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  Run entire university:
    python run_pipeline.py --university "https://www.lmu.de/en/"

  Run only one programme (testing):
    python run_pipeline.py --university "https://www.lmu.de/en/" --programs 1

  Run first five programmes:
    python run_pipeline.py --university "https://www.lmu.de/en/" --programs 5

  Continue past failures:
    python run_pipeline.py --university "https://www.lmu.de/en/" --continue-on-error
        """,
    )

    # Required
    parser.add_argument(
        "--university",
        required=True,
        help="University base URL (e.g. https://www.lmu.de/en/)",
    )

    # Optional
    parser.add_argument(
        "--programs",
        type=int,
        default=None,
        help="Limit to first N discovered programmes (for testing)",
    )

    parser.add_argument(
        "--country",
        type=str,
        default=None,
        help="Country name for workspace organization (auto-detected from URL if omitted)",
    )

    parser.add_argument(
        "--workspace",
        type=str,
        default="data",
        help="Root directory for output data (default: data)",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=False,
        help="Skip failed programmes instead of stopping (default: stop on first error)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print extra debug information",
    )

    return parser.parse_args()


# ==============================================================
# Validation
# ==============================================================

def validate_args(args):
    """
    Validate CLI arguments and exit with a clear error
    message if anything is wrong.
    """

    # --university: must be a valid URL
    parsed = urlparse(args.university)

    if parsed.scheme not in ("http", "https"):
        print(
            f"Error: Invalid university URL: {args.university}\n"
            f"  The URL must start with http:// or https://\n"
            f"  Example: python run_pipeline.py "
            f'--university "https://www.lmu.de/en/"'
        )
        sys.exit(1)

    if not parsed.netloc:
        print(
            f"Error: Invalid university URL: {args.university}\n"
            f"  No domain found in the URL.\n"
            f"  Example: python run_pipeline.py "
            f'--university "https://www.lmu.de/en/"'
        )
        sys.exit(1)

    # --programs: must be a positive integer
    if args.programs is not None and args.programs <= 0:
        print(
            f"Error: --programs must be a positive integer, "
            f"got {args.programs}\n"
            f"  Example: python run_pipeline.py "
            f'--university "https://www.lmu.de/en/" --programs 5'
        )
        sys.exit(1)


# ==============================================================
# Main
# ==============================================================

def main():
    args = parse_args()
    validate_args(args)

    pipeline = UniversityPipeline()

    try:
        result = pipeline.run(
            university_url=args.university,
            program_limit=args.programs,
            country=args.country,
            workspace_dir=args.workspace,
            continue_on_error=args.continue_on_error,
            verbose=args.verbose,
        )

        if result.get("status") == "error":
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        sys.exit(130)

    except Exception as error:
        print(f"\nPipeline failed: {type(error).__name__}: {error}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
