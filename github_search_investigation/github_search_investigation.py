#!/usr/bin/env python3
"""
GitHub Search Coverage Investigation

Tests whether GitHub's search API returns enough quality repos in the
"agentic coding" domain to sustain daily digests.

Target: 150-200 genuinely relevant repos
Requirement: 4 repos/day = ~28/week, ~120/month unique repos

Usage:
    python github_search_investigation.py

    # With a GitHub token for higher rate limits (5000/hr vs 60/hr)
    python github_search_investigation.py --token YOUR_GITHUB_TOKEN

    # Or set environment variable
    set GITHUB_TOKEN=YOUR_TOKEN  (Windows)
    export GITHUB_TOKEN=YOUR_TOKEN  (Linux/Mac)
    python github_search_investigation.py
"""

import sys
import io

# Fix Windows console encoding for unicode characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote

import requests

# Known relevant tools to verify search coverage
KNOWN_TOOLS = [
    ("anthropics/anthropic-cookbook", "Anthropic Cookbook"),
    ("Aider-AI/aider", "Aider"),
    ("continuedev/continue", "Continue"),
    ("getcursor/cursor", "Cursor"),  # May be private
    ("sourcegraph/cody", "Cody"),
    ("TabbyML/tabby", "Tabby"),
    ("cline/cline", "Cline"),
    ("OpenInterpreter/open-interpreter", "Open Interpreter"),
    ("KillianLucas/open-interpreter", "Open Interpreter (alt)"),
    ("Codium-ai/pr-agent", "PR Agent"),
    ("Pythagora-io/gpt-pilot", "GPT Pilot"),
    ("stitionai/devika", "Devika"),
    ("OpenDevin/OpenDevin", "OpenDevin"),
    ("All-Hands-AI/OpenHands", "OpenHands"),
    ("gpt-engineer-org/gpt-engineer", "GPT Engineer"),
    ("AntonOsika/gpt-engineer", "GPT Engineer (original)"),
    ("Significant-Gravitas/AutoGPT", "AutoGPT"),
    ("smol-ai/developer", "Smol Developer"),
    ("plandex-ai/plandex", "Plandex"),
    ("mentat-collective/mentat", "Mentat"),
    ("e2b-dev/e2b", "E2B"),
    ("sweepai/sweep", "Sweep"),
    ("paul-gauthier/aider", "Aider (alt path)"),
]

# Search queries to test
SEARCH_QUERIES = [
    # Topic-based searches
    {"q": "topic:agentic-coding", "desc": "Topic: agentic-coding"},
    {"q": "topic:ai-coding-assistant", "desc": "Topic: ai-coding-assistant"},
    {"q": "topic:ai-code-assistant", "desc": "Topic: ai-code-assistant"},
    {"q": "topic:code-assistant", "desc": "Topic: code-assistant"},
    {"q": "topic:coding-assistant", "desc": "Topic: coding-assistant"},
    {"q": "topic:ai-pair-programming", "desc": "Topic: ai-pair-programming"},
    {"q": "topic:llm-coding", "desc": "Topic: llm-coding"},
    {"q": "topic:ai-developer-tools", "desc": "Topic: ai-developer-tools"},
    {"q": "topic:code-generation", "desc": "Topic: code-generation"},
    {"q": "topic:autonomous-coding", "desc": "Topic: autonomous-coding"},

    # Keyword searches in description/readme
    {"q": '"agentic coding" in:description,readme', "desc": 'Keyword: "agentic coding"'},
    {"q": '"ai coding assistant" in:description,readme', "desc": 'Keyword: "ai coding assistant"'},
    {"q": '"code assistant" "llm" in:description,readme', "desc": 'Keyword: "code assistant" + "llm"'},
    {"q": '"autonomous coding" in:description,readme', "desc": 'Keyword: "autonomous coding"'},
    {"q": '"ai pair programming" in:description,readme', "desc": 'Keyword: "ai pair programming"'},
    {"q": '"coding agent" in:description,readme', "desc": 'Keyword: "coding agent"'},
    {"q": '"code generation" "llm" in:description,readme', "desc": 'Keyword: "code generation" + "llm"'},

    # Broader searches with quality filters
    {"q": "ai code assistant stars:>50", "desc": "AI code assistant (50+ stars)"},
    {"q": "llm coding tool stars:>100", "desc": "LLM coding tool (100+ stars)"},
    {"q": "autonomous developer agent stars:>20", "desc": "Autonomous developer agent (20+ stars)"},
    {"q": "gpt code generation stars:>100", "desc": "GPT code generation (100+ stars)"},
    {"q": "claude coding stars:>10", "desc": "Claude coding (10+ stars)"},
]


@dataclass
class Repo:
    full_name: str
    name: str
    description: str
    stars: int
    forks: int
    updated_at: str
    topics: list
    url: str
    has_readme: bool = True  # Assume true, would need separate API call to verify


class GitHubSearchInvestigator:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        self.session.headers["User-Agent"] = "GitHub-Search-Investigation"

        self.all_repos: dict[str, Repo] = {}
        self.query_results: dict[str, list[str]] = {}
        self.known_tools_found: dict[str, list[str]] = {}

    def check_rate_limit(self):
        """Check current rate limit status."""
        resp = self.session.get("https://api.github.com/rate_limit")
        if resp.status_code == 200:
            data = resp.json()
            search_limit = data["resources"]["search"]
            core_limit = data["resources"]["core"]
            print(f"\n📊 Rate Limits:")
            print(f"   Search: {search_limit['remaining']}/{search_limit['limit']} (resets {datetime.fromtimestamp(search_limit['reset']).strftime('%H:%M:%S')})")
            print(f"   Core:   {core_limit['remaining']}/{core_limit['limit']}")
            return search_limit["remaining"]
        return 0

    def search_repos(self, query: str, max_results: int = 100) -> list[Repo]:
        """Search GitHub repos with the given query."""
        repos = []
        page = 1
        per_page = min(100, max_results)

        while len(repos) < max_results:
            url = f"https://api.github.com/search/repositories"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            }

            resp = self.session.get(url, params=params)

            if resp.status_code == 403:
                print(f"   ⚠️  Rate limited. Waiting 60s...")
                time.sleep(60)
                continue

            if resp.status_code != 200:
                print(f"   ❌ Error {resp.status_code}: {resp.text[:100]}")
                break

            data = resp.json()
            items = data.get("items", [])

            if not items:
                break

            for item in items:
                repo = Repo(
                    full_name=item["full_name"],
                    name=item["name"],
                    description=item.get("description") or "",
                    stars=item["stargazers_count"],
                    forks=item["forks_count"],
                    updated_at=item["updated_at"],
                    topics=item.get("topics", []),
                    url=item["html_url"],
                )
                repos.append(repo)

            if len(items) < per_page:
                break

            page += 1
            time.sleep(2)  # Be nice to the API

        return repos[:max_results]

    def run_query(self, query_info: dict, max_results: int = 100):
        """Run a single search query and collect results."""
        query = query_info["q"]
        desc = query_info["desc"]

        print(f"\n🔍 {desc}")
        print(f"   Query: {query}")

        repos = self.search_repos(query, max_results)

        print(f"   Found: {len(repos)} repos")

        # Track results
        self.query_results[desc] = []
        for repo in repos:
            self.query_results[desc].append(repo.full_name)
            if repo.full_name not in self.all_repos:
                self.all_repos[repo.full_name] = repo

        # Show top 5
        if repos:
            print(f"   Top 5:")
            for repo in repos[:5]:
                print(f"      ⭐ {repo.stars:,} | {repo.full_name}")

        # Show quality floor (last few results)
        if len(repos) >= 10:
            print(f"   Bottom 3 (quality floor):")
            for repo in repos[-3:]:
                desc_preview = (repo.description[:50] + "...") if len(repo.description) > 50 else repo.description
                print(f"      ⭐ {repo.stars:,} | {repo.full_name} | {desc_preview}")

        time.sleep(3)  # Rate limit courtesy

    def check_known_tools(self):
        """Check if known tools appear in search results."""
        print("\n" + "=" * 60)
        print("🎯 CHECKING KNOWN TOOLS COVERAGE")
        print("=" * 60)

        for full_name, tool_name in KNOWN_TOOLS:
            found_in = []
            for query_desc, repo_names in self.query_results.items():
                if full_name.lower() in [r.lower() for r in repo_names]:
                    found_in.append(query_desc)

            if found_in:
                self.known_tools_found[full_name] = found_in
                print(f"✅ {tool_name} ({full_name})")
                print(f"   Found in: {', '.join(found_in[:3])}")
            else:
                # Try to fetch directly to see if it exists
                resp = self.session.get(f"https://api.github.com/repos/{full_name}")
                if resp.status_code == 200:
                    print(f"⚠️  {tool_name} ({full_name}) - EXISTS but NOT in search results")
                elif resp.status_code == 404:
                    print(f"❌ {tool_name} ({full_name}) - Does not exist or is private")
                else:
                    print(f"❓ {tool_name} ({full_name}) - Could not verify")

    def analyze_results(self):
        """Analyze collected results."""
        print("\n" + "=" * 60)
        print("📊 ANALYSIS SUMMARY")
        print("=" * 60)

        # Total unique repos
        print(f"\n📦 Total Unique Repos: {len(self.all_repos)}")

        # Results per query
        print(f"\n📋 Results by Query:")
        for query_desc, repos in sorted(self.query_results.items(), key=lambda x: -len(x[1])):
            print(f"   {len(repos):3d} | {query_desc}")

        # Stars distribution
        print(f"\n⭐ Stars Distribution:")
        stars_buckets = defaultdict(int)
        for repo in self.all_repos.values():
            if repo.stars >= 10000:
                stars_buckets["10000+"] += 1
            elif repo.stars >= 1000:
                stars_buckets["1000-9999"] += 1
            elif repo.stars >= 100:
                stars_buckets["100-999"] += 1
            elif repo.stars >= 50:
                stars_buckets["50-99"] += 1
            elif repo.stars >= 10:
                stars_buckets["10-49"] += 1
            else:
                stars_buckets["<10"] += 1

        for bucket in ["10000+", "1000-9999", "100-999", "50-99", "10-49", "<10"]:
            count = stars_buckets[bucket]
            bar = "█" * (count // 5) if count > 0 else ""
            print(f"   {bucket:>10}: {count:3d} {bar}")

        # Query overlap analysis
        print(f"\n🔀 Query Overlap Analysis:")
        all_repo_names = set()
        for repos in self.query_results.values():
            all_repo_names.update(repos)

        repo_query_count = defaultdict(int)
        for repo_name in all_repo_names:
            for repos in self.query_results.values():
                if repo_name in repos:
                    repo_query_count[repo_name] += 1

        overlap_buckets = defaultdict(int)
        for count in repo_query_count.values():
            overlap_buckets[count] += 1

        print(f"   Repos appearing in N queries:")
        for n in sorted(overlap_buckets.keys(), reverse=True):
            print(f"      {n} queries: {overlap_buckets[n]} repos")

        # Known tools coverage
        print(f"\n🎯 Known Tools Found: {len(self.known_tools_found)}/{len(KNOWN_TOOLS)}")

        # Quality assessment
        print(f"\n✅ VIABILITY ASSESSMENT:")
        total = len(self.all_repos)
        high_quality = sum(1 for r in self.all_repos.values() if r.stars >= 100)
        medium_quality = sum(1 for r in self.all_repos.values() if 50 <= r.stars < 100)

        print(f"   Total unique repos found: {total}")
        print(f"   High quality (100+ stars): {high_quality}")
        print(f"   Medium quality (50-99 stars): {medium_quality}")
        print(f"   Known tools coverage: {len(self.known_tools_found)}/{len(KNOWN_TOOLS)} ({100*len(self.known_tools_found)//len(KNOWN_TOOLS)}%)")

        # Verdict
        print(f"\n" + "=" * 60)
        if total >= 150 and high_quality >= 50:
            print("🟢 VERDICT: VIABLE - Sufficient coverage for daily digests")
        elif total >= 100 and high_quality >= 30:
            print("🟡 VERDICT: MARGINAL - Consider broadening queries or adding seed list")
        else:
            print("🔴 VERDICT: INSUFFICIENT - Need alternative discovery strategy")
        print("=" * 60)

        return {
            "total_repos": total,
            "high_quality": high_quality,
            "medium_quality": medium_quality,
            "known_tools_found": len(self.known_tools_found),
            "known_tools_total": len(KNOWN_TOOLS),
        }

    def export_repos(self, filepath: str):
        """Export all found repos to a JSON file."""
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_repos": len(self.all_repos),
            "repos": [
                {
                    "full_name": r.full_name,
                    "name": r.name,
                    "description": r.description,
                    "stars": r.stars,
                    "forks": r.forks,
                    "updated_at": r.updated_at,
                    "topics": r.topics,
                    "url": r.url,
                }
                for r in sorted(self.all_repos.values(), key=lambda x: -x.stars)
            ],
            "query_results": self.query_results,
            "known_tools_found": self.known_tools_found,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Exported results to: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Investigate GitHub search coverage for agentic coding repos")
    parser.add_argument("--token", help="GitHub personal access token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--max-results", type=int, default=100, help="Max results per query (default: 100)")
    parser.add_argument("--export", default="github_search_results.json", help="Export results to JSON file")
    args = parser.parse_args()

    print("=" * 60)
    print("🔍 GitHub Search Coverage Investigation")
    print("   Target: 150-200 quality repos in 'agentic coding' domain")
    print("=" * 60)

    investigator = GitHubSearchInvestigator(token=args.token)

    # Check rate limit
    remaining = investigator.check_rate_limit()
    if remaining < len(SEARCH_QUERIES):
        print(f"\n⚠️  Warning: Only {remaining} search requests remaining. May not complete all queries.")
        if not args.token:
            print("   Tip: Use --token YOUR_TOKEN for 30 requests/min instead of 10/min")

    # Run all queries
    print("\n" + "=" * 60)
    print("🔎 RUNNING SEARCH QUERIES")
    print("=" * 60)

    for query_info in SEARCH_QUERIES:
        investigator.run_query(query_info, max_results=args.max_results)

    # Check known tools
    investigator.check_known_tools()

    # Analyze results
    results = investigator.analyze_results()

    # Export results
    if args.export:
        investigator.export_repos(args.export)

    return results


if __name__ == "__main__":
    main()
