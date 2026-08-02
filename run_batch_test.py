"""
Batch runner for all 7 university regression tests.
Runs each university sequentially and captures results.
"""

import sys
import time
import traceback
from pipelines.university_pipeline import UniversityPipeline


UNIVERSITIES = [
    {
        "name": "Imperial College London",
        "country": "UK",
        "url": "https://www.imperial.ac.uk/",
        "qs_url": "https://www.topuniversities.com/universities/imperial-college-london",
    },
    {
        "name": "University of Toronto",
        "country": "Canada",
        "url": "https://www.utoronto.ca/",
        "qs_url": "https://www.topuniversities.com/universities/university-toronto",
    },
    {
        "name": "University of Melbourne",
        "country": "Australia",
        "url": "https://www.unimelb.edu.au/",
        "qs_url": "https://www.topuniversities.com/universities/university-melbourne",
    },
    {
        "name": "Sorbonne Universite",
        "country": "France",
        "url": "https://www.sorbonne-universite.fr/en",
        "qs_url": "https://www.topuniversities.com/universities/sorbonne-university",
    },
    {
        "name": "TU Delft",
        "country": "Netherlands",
        "url": "https://www.tudelft.nl/en/education/programmes",
        "qs_url": "https://www.topuniversities.com/universities/delft-university-technology",
    },
    {
        "name": "LMU Munich",
        "country": "Germany",
        "url": "https://www.lmu.de/en/",
        "qs_url": "https://www.topuniversities.com/universities/ludwig-maximilians-universitat-munchen",
    },
    {
        "name": "ETH Zurich",
        "country": "Switzerland",
        "url": "https://ethz.ch/en.html",
        "qs_url": "https://www.topuniversities.com/universities/eth-zurich-swiss-federal-institute-technology",
    },
]


def main():
    pipeline = UniversityPipeline()
    results = []

    total = len(UNIVERSITIES)

    print()
    print("=" * 70)
    print(f"  BATCH REGRESSION TEST — {total} Universities")
    print("=" * 70)
    print()

    for index, uni in enumerate(UNIVERSITIES, start=1):

        print()
        print("*" * 70)
        print(f"  [{index}/{total}] {uni['name']} ({uni['country']})")
        print(f"  URL: {uni['url']}")
        print(f"  QS:  {uni['qs_url']}")
        print("*" * 70)
        print()

        start_time = time.time()

        try:
            result = pipeline.run(
                university_url=uni["url"],
                program_limit=1,
                continue_on_error=True,
                qs_profile_url=uni["qs_url"],
            )

            elapsed = time.time() - start_time

            results.append({
                "name": uni["name"],
                "status": result.get("status", "unknown"),
                "programs_discovered": result.get("programs_discovered", 0),
                "programs_succeeded": result.get("programs_succeeded", 0),
                "programs_failed": result.get("programs_failed", 0),
                "elapsed": round(elapsed, 1),
                "error": None,
            })

        except Exception as error:

            elapsed = time.time() - start_time

            results.append({
                "name": uni["name"],
                "status": "crashed",
                "programs_discovered": 0,
                "programs_succeeded": 0,
                "programs_failed": 0,
                "elapsed": round(elapsed, 1),
                "error": f"{type(error).__name__}: {error}",
            })

            print(f"\n  CRASHED: {type(error).__name__}: {error}")
            traceback.print_exc()

    # ---- Final Summary ----
    print()
    print()
    print("=" * 70)
    print("  BATCH RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"  {'University':<30} {'Status':<12} {'Disc':>5} {'OK':>4} {'Fail':>4} {'Time':>8}")
    print("  " + "-" * 67)

    for r in results:
        status_icon = {
            "success": "✓",
            "partial": "⚠",
            "error": "✗",
            "crashed": "💥",
        }.get(r["status"], "?")

        print(
            f"  {r['name']:<30} {status_icon} {r['status']:<10} "
            f"{r['programs_discovered']:>5} {r['programs_succeeded']:>4} "
            f"{r['programs_failed']:>4} {r['elapsed']:>6.1f}s"
        )

        if r["error"]:
            print(f"    Error: {r['error']}")

    succeeded = sum(1 for r in results if r["status"] == "success")
    total_time = sum(r["elapsed"] for r in results)

    print()
    print(f"  Total: {succeeded}/{total} fully succeeded in {total_time:.0f}s")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
