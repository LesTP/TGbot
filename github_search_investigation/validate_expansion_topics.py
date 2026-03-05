#!/usr/bin/env python3
"""
Expansion Topic Validation

Checks each proposed expansion topic to verify:
1. Total volume (how many repos?)
2. Overlap with coding-assistant (what % are actually relevant?)

Helps filter out overly broad topics like "developer-tools" that might
return too much noise.
"""

import sys
import io
import os
import time
import argparse
from dataclasses import dataclass

import requests

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# Primary topic to check overlap against
PRIMARY_TOPIC = "coding-assistant"

# Expansion topics to validate
EXPANSION_TOPICS = [
    "developer-tools",
    "claude-code",
    "ai-agents",
    "ai-coding",
    "mcp",
    "vibe-coding",
    "codegen",
    "agentic-ai",
    "agents",
    "ai-tools",
]

# Additional topics from the co-occurrence analysis to consider
ADDITIONAL_CANDIDATES = [
    "anthropic",
    "gpt-4",
    "cursor",
    "ai-assistant",
    "ai-agent",
    "prompt-engineering",
    "llm-agent",
    "code-analyzer",
    "ai-code-review",
]


@dataclass
class TopicStats:
    topic: str
    total_count: int
    overlap_count: int
    overlap_pct: float
    sample_repos: list[str]
    recommendation: str


class TopicValidator:
    def __init__(self, token: str = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self.session.headers["User-Agent"] = "Topic-Validator"

        self.primary_repos: set[str] = set()

    def get_topic_count(self, topic: str) -> int:
        """Get total repo count for a topic."""
        url = "https://api.github.com/search/repositories"
        params = {"q": f"topic:{topic}", "per_page": 1}

        resp = self.session.get(url, params=params)
        if resp.status_code == 200:
            return resp.json().get("total_count", 0)
        return 0

    def get_topic_repos(self, topic: str, max_results: int = 200) -> list[str]:
        """Get repo names for a topic."""
        repos = []
        page = 1

        while len(repos) < max_results:
            url = "https://api.github.com/search/repositories"
            params = {
                "q": f"topic:{topic} stars:>10",
                "sort": "stars",
                "order": "desc",
                "per_page": 100,
                "page": page,
            }

            resp = self.session.get(url, params=params)

            if resp.status_code == 403:
                print(f"   ⚠️  Rate limited, waiting 60s...")
                time.sleep(60)
                continue

            if resp.status_code != 200:
                break

            items = resp.json().get("items", [])
            if not items:
                break

            for item in items:
                repos.append(item["full_name"])

            if len(items) < 100:
                break

            page += 1
            time.sleep(2)

        return repos[:max_results]

    def load_primary_repos(self):
        """Load repos from the primary topic for overlap checking."""
        print(f"Loading primary topic: {PRIMARY_TOPIC}...")
        repos = self.get_topic_repos(PRIMARY_TOPIC, max_results=500)
        self.primary_repos = set(repos)
        print(f"  Found {len(self.primary_repos)} repos")
        time.sleep(3)

    def validate_topic(self, topic: str) -> TopicStats:
        """Validate a single expansion topic."""
        print(f"\n🔍 Validating: topic:{topic}")

        # Get total count
        total_count = self.get_topic_count(topic)
        print(f"   Total repos: {total_count:,}")
        time.sleep(2)

        # Get repos for overlap check
        repos = self.get_topic_repos(topic, max_results=200)
        time.sleep(3)

        # Calculate overlap
        repo_set = set(repos)
        overlap = repo_set & self.primary_repos
        overlap_count = len(overlap)
        overlap_pct = (overlap_count / len(repos) * 100) if repos else 0

        print(f"   Sample size: {len(repos)}")
        print(f"   Overlap with {PRIMARY_TOPIC}: {overlap_count} ({overlap_pct:.1f}%)")

        # Get sample repos (top 3 that overlap, top 3 that don't)
        overlapping = list(overlap)[:3]
        non_overlapping = [r for r in repos[:10] if r not in overlap][:3]

        # Determine recommendation
        if total_count > 10000 and overlap_pct < 10:
            recommendation = "❌ SKIP - Too broad, low overlap"
        elif total_count > 5000 and overlap_pct < 15:
            recommendation = "⚠️  CAUTION - Broad, needs filtering"
        elif overlap_pct >= 30:
            recommendation = "✅ INCLUDE - High overlap"
        elif overlap_pct >= 15:
            recommendation = "✅ INCLUDE - Moderate overlap"
        elif total_count < 500 and overlap_pct >= 5:
            recommendation = "✅ INCLUDE - Niche but relevant"
        else:
            recommendation = "❓ REVIEW - Manual check needed"

        print(f"   Recommendation: {recommendation}")

        if overlapping:
            print(f"   Overlapping samples: {', '.join(overlapping[:3])}")
        if non_overlapping:
            print(f"   Non-overlapping samples: {', '.join(non_overlapping[:3])}")

        return TopicStats(
            topic=topic,
            total_count=total_count,
            overlap_count=overlap_count,
            overlap_pct=overlap_pct,
            sample_repos=repos[:10],
            recommendation=recommendation,
        )


def main():
    parser = argparse.ArgumentParser(description="Validate expansion topics")
    parser.add_argument("--token", help="GitHub token")
    parser.add_argument("--include-additional", action="store_true",
                        help="Also check additional candidate topics")
    args = parser.parse_args()

    print("=" * 70)
    print("🔬 Expansion Topic Validation")
    print("=" * 70)

    validator = TopicValidator(token=args.token)

    # Load primary topic
    validator.load_primary_repos()

    # Validate expansion topics
    topics_to_check = EXPANSION_TOPICS.copy()
    if args.include_additional:
        topics_to_check.extend(ADDITIONAL_CANDIDATES)

    results: list[TopicStats] = []

    print("\n" + "-" * 70)
    print("📊 Validating Expansion Topics")
    print("-" * 70)

    for topic in topics_to_check:
        try:
            stats = validator.validate_topic(topic)
            results.append(stats)
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)

    print(f"\n{'Topic':<25} {'Total':>8} {'Overlap':>8} {'%':>6} Recommendation")
    print("-" * 70)

    # Sort by overlap percentage descending
    results.sort(key=lambda x: -x.overlap_pct)

    for r in results:
        total_str = f"{r.total_count:,}" if r.total_count < 100000 else f"{r.total_count//1000}k+"
        print(f"{r.topic:<25} {total_str:>8} {r.overlap_count:>8} {r.overlap_pct:>5.1f}% {r.recommendation}")

    # Final recommendations
    print("\n" + "=" * 70)
    print("📝 FINAL RECOMMENDATIONS")
    print("=" * 70)

    include = [r for r in results if "INCLUDE" in r.recommendation]
    skip = [r for r in results if "SKIP" in r.recommendation]
    caution = [r for r in results if "CAUTION" in r.recommendation]
    review = [r for r in results if "REVIEW" in r.recommendation]

    if include:
        print(f"\n✅ INCLUDE ({len(include)}):")
        for r in include:
            print(f"   topic:{r.topic}")

    if caution:
        print(f"\n⚠️  USE WITH HIGHER MIN_STARS ({len(caution)}):")
        for r in caution:
            print(f"   topic:{r.topic} (suggest min_stars: 200+)")

    if skip:
        print(f"\n❌ SKIP ({len(skip)}):")
        for r in skip:
            print(f"   topic:{r.topic} ({r.total_count:,} repos, {r.overlap_pct:.1f}% overlap)")

    if review:
        print(f"\n❓ MANUAL REVIEW ({len(review)}):")
        for r in review:
            print(f"   topic:{r.topic}")


if __name__ == "__main__":
    main()
