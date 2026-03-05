#!/usr/bin/env python3
"""
Topic Co-occurrence Analysis

Analyzes topics from discovered repos to find related search terms
that could expand discovery coverage.

Uses the repos already found in github_search_results.json to build
a topic graph and identify high-frequency co-occurring topics.
"""

import sys
import io
import json
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


# Current search topics (from github_search_investigation.py)
CURRENT_SEARCH_TOPICS = {
    "agentic-coding",
    "ai-coding-assistant",
    "ai-code-assistant",
    "code-assistant",
    "coding-assistant",
    "ai-pair-programming",
    "llm-coding",
    "ai-developer-tools",
    "code-generation",
    "autonomous-coding",
}

# Noise topics to filter out (too generic)
NOISE_TOPICS = {
    "python", "typescript", "javascript", "go", "rust", "java", "ruby",
    "hacktoberfest", "opensource", "open-source",
    "windows", "linux", "macos", "docker",
    "api", "cli", "sdk", "library", "framework", "tool", "tools",
    "awesome", "awesome-list", "list",
}


def load_repos(filepath: str, min_stars: int = 100) -> list[dict]:
    """Load repos from JSON file, filtering by minimum stars."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    repos = [r for r in data["repos"] if r["stars"] >= min_stars]
    print(f"Loaded {len(repos)} repos with {min_stars}+ stars")
    return repos


def extract_topics(repos: list[dict]) -> tuple[Counter, dict]:
    """Extract all topics and their frequency."""
    topic_counts = Counter()
    topic_to_repos = defaultdict(list)

    for repo in repos:
        topics = repo.get("topics", [])
        for topic in topics:
            topic_lower = topic.lower()
            topic_counts[topic_lower] += 1
            topic_to_repos[topic_lower].append(repo["full_name"])

    return topic_counts, topic_to_repos


def build_cooccurrence_matrix(repos: list[dict]) -> dict[tuple, int]:
    """Build topic co-occurrence matrix."""
    cooccurrence = Counter()

    for repo in repos:
        topics = [t.lower() for t in repo.get("topics", [])]
        # Generate all pairs of topics in this repo
        for pair in combinations(sorted(topics), 2):
            cooccurrence[pair] += 1

    return cooccurrence


def find_related_topics(cooccurrence: dict, seed_topics: set, min_cooccurrence: int = 3) -> dict:
    """Find topics that frequently co-occur with seed topics."""
    related = defaultdict(lambda: {"count": 0, "co_occurs_with": []})

    for (topic1, topic2), count in cooccurrence.items():
        if count < min_cooccurrence:
            continue

        # Check if one of the pair is a seed topic
        if topic1 in seed_topics and topic2 not in seed_topics:
            related[topic2]["count"] += count
            related[topic2]["co_occurs_with"].append((topic1, count))
        elif topic2 in seed_topics and topic1 not in seed_topics:
            related[topic1]["count"] += count
            related[topic1]["co_occurs_with"].append((topic2, count))

    return related


def analyze_topic_clusters(cooccurrence: dict, topic_counts: Counter, min_count: int = 5) -> list[set]:
    """Identify clusters of frequently co-occurring topics."""
    # Build adjacency list
    adjacency = defaultdict(set)
    for (topic1, topic2), count in cooccurrence.items():
        if count >= min_count:
            adjacency[topic1].add(topic2)
            adjacency[topic2].add(topic1)

    # Find connected components (simple DFS)
    visited = set()
    clusters = []

    for topic in adjacency:
        if topic in visited:
            continue

        cluster = set()
        stack = [topic]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            cluster.add(current)
            stack.extend(adjacency[current] - visited)

        if len(cluster) >= 3:  # Only keep meaningful clusters
            clusters.append(cluster)

    return sorted(clusters, key=len, reverse=True)


def main():
    print("=" * 70)
    print("🔬 Topic Co-occurrence Analysis")
    print("=" * 70)

    # Load data
    results_file = Path(__file__).parent / "github_search_results.json"
    if not results_file.exists():
        print(f"❌ Error: {results_file} not found. Run github_search_investigation.py first.")
        return

    repos = load_repos(results_file, min_stars=100)

    # Extract topics
    print("\n" + "-" * 70)
    print("📊 Topic Frequency Analysis")
    print("-" * 70)

    topic_counts, topic_to_repos = extract_topics(repos)

    print(f"\nTotal unique topics: {len(topic_counts)}")
    print(f"\nTop 30 most common topics:")
    for topic, count in topic_counts.most_common(30):
        in_search = "✓" if topic in CURRENT_SEARCH_TOPICS else " "
        noise = "~" if topic in NOISE_TOPICS else " "
        print(f"  {in_search}{noise} {count:3d} | {topic}")

    # Build co-occurrence matrix
    print("\n" + "-" * 70)
    print("🔗 Topic Co-occurrence Analysis")
    print("-" * 70)

    cooccurrence = build_cooccurrence_matrix(repos)
    print(f"\nTotal topic pairs: {len(cooccurrence)}")

    # Find strongest co-occurrences
    print(f"\nTop 20 strongest co-occurring pairs:")
    for (t1, t2), count in cooccurrence.most_common(20):
        print(f"  {count:3d} | {t1} <-> {t2}")

    # Find topics related to our seed topics
    print("\n" + "-" * 70)
    print("🎯 Topics Related to Current Search Terms")
    print("-" * 70)

    related = find_related_topics(cooccurrence, CURRENT_SEARCH_TOPICS, min_cooccurrence=2)

    # Filter out noise and already-used topics
    candidates = []
    for topic, data in related.items():
        if topic in NOISE_TOPICS or topic in CURRENT_SEARCH_TOPICS:
            continue
        candidates.append((topic, data["count"], data["co_occurs_with"]))

    candidates.sort(key=lambda x: -x[1])

    print(f"\nCandidate expansion topics (co-occur with current search terms):")
    print(f"{'Topic':<35} {'Score':>5} | Co-occurs with")
    print("-" * 70)

    for topic, score, co_occurs in candidates[:30]:
        co_list = ", ".join([f"{t}({c})" for t, c in sorted(co_occurs, key=lambda x: -x[1])[:3]])
        print(f"  {topic:<33} {score:>5} | {co_list}")

    # Identify topic clusters
    print("\n" + "-" * 70)
    print("🌐 Topic Clusters (frequently co-occurring groups)")
    print("-" * 70)

    clusters = analyze_topic_clusters(cooccurrence, topic_counts, min_count=3)

    for i, cluster in enumerate(clusters[:10], 1):
        # Sort by frequency
        sorted_cluster = sorted(cluster, key=lambda t: -topic_counts[t])
        cluster_str = ", ".join(sorted_cluster[:10])
        if len(sorted_cluster) > 10:
            cluster_str += f" ... (+{len(sorted_cluster) - 10} more)"
        print(f"\n  Cluster {i} ({len(cluster)} topics):")
        print(f"    {cluster_str}")

    # Generate recommendations
    print("\n" + "=" * 70)
    print("📋 RECOMMENDATIONS")
    print("=" * 70)

    print("\n🟢 HIGH-VALUE expansion topics (add to search config):")
    high_value = [c for c in candidates if c[1] >= 5 and len(c[0]) > 3][:15]
    for topic, score, _ in high_value:
        example_repos = topic_to_repos.get(topic, [])[:3]
        print(f"  + topic:{topic}")
        if example_repos:
            print(f"      Examples: {', '.join(example_repos)}")

    print("\n🟡 MEDIUM-VALUE topics (review manually):")
    medium_value = [c for c in candidates if 3 <= c[1] < 5 and len(c[0]) > 3][:10]
    for topic, score, _ in medium_value:
        print(f"  ? topic:{topic} (score: {score})")

    # Export detailed results
    output_file = Path(__file__).parent / "topic_analysis_results.json"
    export_data = {
        "topic_counts": dict(topic_counts.most_common(200)),
        "top_cooccurrences": [(list(pair), count) for pair, count in cooccurrence.most_common(100)],
        "expansion_candidates": [
            {"topic": t, "score": s, "co_occurs_with": co}
            for t, s, co in candidates[:50]
        ],
        "clusters": [list(c) for c in clusters[:10]],
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2)

    print(f"\n💾 Detailed results exported to: {output_file}")

    # Summary
    print("\n" + "=" * 70)
    print("📈 SUMMARY")
    print("=" * 70)
    print(f"  Repos analyzed: {len(repos)}")
    print(f"  Unique topics found: {len(topic_counts)}")
    print(f"  Current search topics: {len(CURRENT_SEARCH_TOPICS)}")
    print(f"  Expansion candidates identified: {len(candidates)}")
    print(f"  High-value additions: {len(high_value)}")


if __name__ == "__main__":
    main()
