"""Crawl statistics report generator for the GlobalNews pipeline.

Produces a structured JSON report summarizing crawl results across all
sites for a single crawl run. The report includes per-site statistics,
failure analysis, retry metrics, and timing data.

Report output: ``data/raw/YYYY-MM-DD/crawl_report.json``

Reference:
    Step 5 Architecture Blueprint, Section 6 (Observability).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.crawling.contracts import CrawlResult

import logging

logger = logging.getLogger(__name__)


def generate_crawl_report(
    results: list[CrawlResult],
    crawl_date: str,
    elapsed_seconds: float,
    retry_stats: dict[str, Any] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate a structured crawl report from CrawlResult objects.

    Produces a JSON-serializable dictionary with aggregate and per-site
    statistics. Optionally writes the report to disk.

    Args:
        results: List of CrawlResult objects, one per crawled site.
        crawl_date: Date string (YYYY-MM-DD) for this crawl run.
        elapsed_seconds: Total wall-clock time for the pipeline.
        retry_stats: Optional retry statistics from RetryManager.
        output_dir: Directory to write the report JSON. If None,
            the report is returned but not written.

    Returns:
        Report dictionary with the following structure:
        - date: Crawl date
        - total_articles: Sum of extracted articles
        - total_sites_attempted: Number of sites processed
        - sites_succeeded: Sites with at least 1 article
        - sites_failed: Sites with 0 articles and errors
        - per_site: Per-site detail dictionaries
        - failed_sites: List of failure summaries
        - elapsed_seconds: Total pipeline duration
        - retry_stats: Per-level retry counts
    """
    total_articles = 0
    sites_succeeded = 0
    sites_failed = 0
    per_site: dict[str, dict[str, Any]] = {}
    failed_sites: list[dict[str, Any]] = []

    for result in results:
        site_id = result.source_id
        articles_count = result.extracted_count
        total_articles += articles_count

        site_entry: dict[str, Any] = {
            "articles": articles_count,
            "urls_discovered": result.discovered_urls,
            "urls_deduped": result.skipped_dedup_count,
            "freshness_filtered": result.skipped_freshness_count,
            "failed": result.failed_count,
            "time_seconds": round(result.elapsed_seconds, 1),
            "max_tier": result.tier_used,
        }
        per_site[site_id] = site_entry

        if articles_count > 0:
            sites_succeeded += 1
        elif result.errors:
            sites_failed += 1
            # Summarize the primary failure reason
            primary_reason = result.errors[0] if result.errors else "Unknown"
            if len(primary_reason) > 200:
                primary_reason = primary_reason[:200] + "..."

            failed_sites.append({
                "site_id": site_id,
                "reason": primary_reason,
                "articles": articles_count,
                "tier_reached": result.tier_used,
                "error_count": len(result.errors),
            })
        else:
            # No articles, no errors -- probably disabled or no URLs discovered
            pass

    report: dict[str, Any] = {
        "date": crawl_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_articles": total_articles,
        "total_sites_attempted": len(results),
        "sites_succeeded": sites_succeeded,
        "sites_failed": sites_failed,
        "sites_skipped": len(results) - sites_succeeded - sites_failed,
        "per_site": per_site,
        "failed_sites": failed_sites,
        "elapsed_seconds": round(elapsed_seconds, 1),
        "retry_stats": retry_stats or {
            "level1": 0, "level2": 0, "level3": 0, "level4": 0,
        },
        "summary": {
            "average_articles_per_site": (
                round(total_articles / sites_succeeded, 1)
                if sites_succeeded > 0
                else 0
            ),
            "success_rate": (
                round(sites_succeeded / len(results) * 100, 1)
                if results
                else 0
            ),
            "total_urls_discovered": sum(r.discovered_urls for r in results),
            "total_urls_deduped": sum(r.skipped_dedup_count for r in results),
            "total_freshness_filtered": sum(r.skipped_freshness_count for r in results),
            "total_urls_failed": sum(r.failed_count for r in results),
        },
    }

    # Write to disk if output_dir specified
    if output_dir is not None:
        _write_report(report, output_dir, crawl_date)

    return report


def _write_report(
    report: dict[str, Any],
    output_dir: Path,
    crawl_date: str,
) -> Path:
    """Write the crawl report to a JSON file atomically.

    Uses temp file + atomic rename to prevent partial writes.

    Args:
        report: The report dictionary.
        output_dir: Directory containing the day's crawl output.
        crawl_date: Date string for filename.

    Returns:
        Path to the written report file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "crawl_report.json"

    fd, temp_str = tempfile.mkstemp(
        suffix=".json.tmp",
        dir=str(output_dir),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        os.replace(temp_str, str(report_path))
    except OSError:
        if os.path.exists(temp_str):
            os.unlink(temp_str)
        raise

    logger.info(
        "crawl_report_written path=%s articles=%s sites=%s",
        str(report_path), report["total_articles"], report["total_sites_attempted"],
    )

    return report_path


def print_crawl_summary(report: dict[str, Any]) -> None:
    """Print a human-readable crawl summary to stdout.

    Args:
        report: The crawl report dictionary.
    """
    print()
    print("=" * 70)
    print(f"  CRAWL REPORT -- {report['date']}")
    print("=" * 70)
    print()
    print(f"  Total articles collected:  {report['total_articles']}")
    print(f"  Sites attempted:           {report['total_sites_attempted']}")
    print(f"  Sites succeeded:           {report['sites_succeeded']}")
    print(f"  Sites failed:              {report['sites_failed']}")
    print(f"  Sites skipped:             {report.get('sites_skipped', 0)}")
    print(f"  Elapsed time:              {report['elapsed_seconds']}s")
    print()

    summary = report.get("summary", {})
    print(f"  Avg articles/site:         {summary.get('average_articles_per_site', 0)}")
    print(f"  Success rate:              {summary.get('success_rate', 0)}%")
    print(f"  URLs discovered:           {summary.get('total_urls_discovered', 0)}")
    print(f"  URLs deduped:              {summary.get('total_urls_deduped', 0)}")
    print(f"  Freshness filtered (>24h): {summary.get('total_freshness_filtered', 0)}")
    print(f"  URLs failed:               {summary.get('total_urls_failed', 0)}")
    print()

    retry_stats = report.get("retry_stats", {})
    if any(retry_stats.get(f"level{i}", 0) > 0 for i in range(1, 5)):
        print("  Retry Statistics:")
        for level in range(1, 5):
            count = retry_stats.get(f"level{level}", 0)
            if count > 0:
                print(f"    Level {level}: {count} retries")
        print()

    failed = report.get("failed_sites", [])
    if failed:
        print(f"  Failed Sites ({len(failed)}):")
        for site in failed:
            print(f"    - {site['site_id']}: {site['reason'][:80]}")
        print()

    # Top 10 sites by article count
    per_site = report.get("per_site", {})
    if per_site:
        sorted_sites = sorted(
            per_site.items(),
            key=lambda x: x[1].get("articles", 0),
            reverse=True,
        )
        top_sites = sorted_sites[:10]
        print("  Top 10 Sites by Articles:")
        for site_id, stats in top_sites:
            print(
                f"    {site_id:20s}  {stats['articles']:>4d} articles  "
                f"({stats['urls_discovered']} discovered, "
                f"{stats['time_seconds']}s)"
            )
        print()

    print("=" * 70)
    print()
