#!/usr/bin/env python3
"""
GitHub Search Investigation - Chart Generator

Generates an interactive HTML report with charts from the investigation data.
Uses Chart.js from CDN - no Python dependencies beyond built-in modules.

Usage:
    python generate_charts.py

Output:
    investigation_charts.html (open in any browser)
"""

import json
import html
from datetime import datetime
from pathlib import Path


def load_json(filepath: str) -> dict:
    """Load JSON data from file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_html_report(
    search_results: dict,
    topic_analysis: dict,
    output_path: str
):
    """Generate the HTML report with embedded charts."""

    # Process data for charts
    repos = search_results.get("repos", [])

    # Stars distribution
    stars_buckets = {"10000+": 0, "1000-9999": 0, "100-999": 0, "50-99": 0, "10-49": 0, "<10": 0}
    for repo in repos:
        stars = repo["stars"]
        if stars >= 10000:
            stars_buckets["10000+"] += 1
        elif stars >= 1000:
            stars_buckets["1000-9999"] += 1
        elif stars >= 100:
            stars_buckets["100-999"] += 1
        elif stars >= 50:
            stars_buckets["50-99"] += 1
        elif stars >= 10:
            stars_buckets["10-49"] += 1
        else:
            stars_buckets["<10"] += 1

    # Query results
    query_results = search_results.get("query_results", {})
    query_labels = list(query_results.keys())
    query_counts = [len(v) for v in query_results.values()]

    # Sort by count descending
    sorted_queries = sorted(zip(query_labels, query_counts), key=lambda x: -x[1])
    query_labels = [q[0] for q in sorted_queries]
    query_counts = [q[1] for q in sorted_queries]

    # Topic frequency (top 20)
    topic_counts = topic_analysis.get("topic_counts", {})
    top_topics = list(topic_counts.items())[:20]
    topic_labels = [t[0] for t in top_topics]
    topic_values = [t[1] for t in top_topics]

    # Co-occurrence data (top 15)
    cooccurrences = topic_analysis.get("top_cooccurrences", [])[:15]
    cooc_labels = [f"{pair[0][0]} + {pair[0][1]}" for pair in cooccurrences]
    cooc_values = [pair[1] for pair in cooccurrences]

    # Expansion candidates
    candidates = topic_analysis.get("expansion_candidates", [])[:15]
    candidate_labels = [c["topic"] for c in candidates]
    candidate_scores = [c["score"] for c in candidates]

    # Top repos by stars
    top_repos = repos[:20]
    repo_labels = [r["name"][:20] for r in top_repos]
    repo_stars = [r["stars"] for r in top_repos]

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Search Investigation Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        h1 {{
            text-align: center;
            color: #24292e;
            border-bottom: 2px solid #0366d6;
            padding-bottom: 15px;
        }}
        h2 {{
            color: #24292e;
            margin-top: 40px;
            border-left: 4px solid #0366d6;
            padding-left: 15px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-card .number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #0366d6;
        }}
        .stat-card .label {{
            color: #586069;
            margin-top: 5px;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 20px 0;
        }}
        .chart-row {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}
        .chart-wrapper {{
            position: relative;
            height: 400px;
        }}
        .chart-wrapper.tall {{
            height: 500px;
        }}
        .footer {{
            text-align: center;
            color: #586069;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e1e4e8;
        }}
        .verdict {{
            background: #dcffe4;
            border: 2px solid #34d058;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            font-size: 1.2em;
            margin: 30px 0;
        }}
        .verdict.viable {{
            background: #dcffe4;
            border-color: #34d058;
        }}
    </style>
</head>
<body>
    <h1>🔍 GitHub Search Investigation Report</h1>
    <p style="text-align: center; color: #586069;">
        Agentic Coding Domain Analysis | Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}
    </p>

    <div class="verdict viable">
        🟢 <strong>VERDICT: VIABLE</strong> — Sufficient coverage for daily digests
    </div>

    <div class="summary">
        <div class="stat-card">
            <div class="number">{len(repos):,}</div>
            <div class="label">Total Unique Repos</div>
        </div>
        <div class="stat-card">
            <div class="number">{sum(1 for r in repos if r['stars'] >= 100):,}</div>
            <div class="label">High Quality (100+ ⭐)</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(query_results)}</div>
            <div class="label">Search Queries Tested</div>
        </div>
        <div class="stat-card">
            <div class="number">{len(topic_counts)}</div>
            <div class="label">Unique Topics Found</div>
        </div>
    </div>

    <h2>📊 Stars Distribution</h2>
    <div class="chart-container">
        <div class="chart-wrapper">
            <canvas id="starsChart"></canvas>
        </div>
    </div>

    <h2>🔎 Results by Search Query</h2>
    <div class="chart-container">
        <div class="chart-wrapper tall">
            <canvas id="queryChart"></canvas>
        </div>
    </div>

    <div class="chart-row">
        <div>
            <h2>🏷️ Top Topics</h2>
            <div class="chart-container">
                <div class="chart-wrapper tall">
                    <canvas id="topicsChart"></canvas>
                </div>
            </div>
        </div>
        <div>
            <h2>🔗 Topic Co-occurrences</h2>
            <div class="chart-container">
                <div class="chart-wrapper tall">
                    <canvas id="cooccurrenceChart"></canvas>
                </div>
            </div>
        </div>
    </div>

    <h2>🎯 Expansion Candidates</h2>
    <p style="color: #586069;">Topics that frequently co-occur with current search terms (potential additions)</p>
    <div class="chart-container">
        <div class="chart-wrapper">
            <canvas id="candidatesChart"></canvas>
        </div>
    </div>

    <h2>⭐ Top Repos by Stars</h2>
    <div class="chart-container">
        <div class="chart-wrapper tall">
            <canvas id="reposChart"></canvas>
        </div>
    </div>

    <div class="footer">
        <p>Data source: GitHub Search API | Analysis for GitHub Digest Bot project</p>
    </div>

    <script>
        // Color palette
        const colors = {{
            blue: 'rgba(54, 162, 235, 0.8)',
            green: 'rgba(75, 192, 192, 0.8)',
            orange: 'rgba(255, 159, 64, 0.8)',
            purple: 'rgba(153, 102, 255, 0.8)',
            red: 'rgba(255, 99, 132, 0.8)',
            yellow: 'rgba(255, 205, 86, 0.8)',
        }};

        const borderColors = {{
            blue: 'rgba(54, 162, 235, 1)',
            green: 'rgba(75, 192, 192, 1)',
            orange: 'rgba(255, 159, 64, 1)',
            purple: 'rgba(153, 102, 255, 1)',
            red: 'rgba(255, 99, 132, 1)',
            yellow: 'rgba(255, 205, 86, 1)',
        }};

        // Stars Distribution Chart
        new Chart(document.getElementById('starsChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(list(stars_buckets.keys()))},
                datasets: [{{
                    label: 'Number of Repos',
                    data: {json.dumps(list(stars_buckets.values()))},
                    backgroundColor: [
                        colors.purple, colors.blue, colors.green,
                        colors.yellow, colors.orange, colors.red
                    ],
                    borderColor: [
                        borderColors.purple, borderColors.blue, borderColors.green,
                        borderColors.yellow, borderColors.orange, borderColors.red
                    ],
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{ display: true, text: 'Repository Distribution by Star Count' }}
                }},
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Query Results Chart
        new Chart(document.getElementById('queryChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(query_labels)},
                datasets: [{{
                    label: 'Repos Found',
                    data: {json.dumps(query_counts)},
                    backgroundColor: colors.blue,
                    borderColor: borderColors.blue,
                    borderWidth: 1
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{ display: true, text: 'Search Results by Query' }}
                }},
                scales: {{
                    x: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Topics Chart
        new Chart(document.getElementById('topicsChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(topic_labels)},
                datasets: [{{
                    label: 'Frequency',
                    data: {json.dumps(topic_values)},
                    backgroundColor: colors.green,
                    borderColor: borderColors.green,
                    borderWidth: 1
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{ display: true, text: 'Most Common Topics' }}
                }},
                scales: {{
                    x: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Co-occurrence Chart
        new Chart(document.getElementById('cooccurrenceChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(cooc_labels)},
                datasets: [{{
                    label: 'Co-occurrence Count',
                    data: {json.dumps(cooc_values)},
                    backgroundColor: colors.purple,
                    borderColor: borderColors.purple,
                    borderWidth: 1
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{ display: true, text: 'Topic Pairs Appearing Together' }}
                }},
                scales: {{
                    x: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Expansion Candidates Chart
        new Chart(document.getElementById('candidatesChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(candidate_labels)},
                datasets: [{{
                    label: 'Relevance Score',
                    data: {json.dumps(candidate_scores)},
                    backgroundColor: colors.orange,
                    borderColor: borderColors.orange,
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{ display: true, text: 'Potential Expansion Topics (by co-occurrence with current search terms)' }}
                }},
                scales: {{
                    y: {{ beginAtZero: true }}
                }}
            }}
        }});

        // Top Repos Chart
        new Chart(document.getElementById('reposChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(repo_labels)},
                datasets: [{{
                    label: 'Stars',
                    data: {json.dumps(repo_stars)},
                    backgroundColor: colors.yellow,
                    borderColor: borderColors.yellow,
                    borderWidth: 1
                }}]
            }},
            options: {{
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    title: {{ display: true, text: 'Top Discovered Repositories' }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        ticks: {{
                            callback: function(value) {{
                                return value >= 1000 ? (value/1000) + 'k' : value;
                            }}
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Generated: {output_path}")
    print(f"   Open in browser to view interactive charts")


def main():
    import sys
    import io

    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    script_dir = Path(__file__).parent

    # Load data files
    search_results_path = script_dir / "github_search_results.json"
    topic_analysis_path = script_dir / "topic_analysis_results.json"
    output_path = script_dir / "investigation_charts.html"

    if not search_results_path.exists():
        print(f"❌ Missing: {search_results_path}")
        print("   Run github_search_investigation.py first")
        return

    if not topic_analysis_path.exists():
        print(f"❌ Missing: {topic_analysis_path}")
        print("   Run topic_cooccurrence_analysis.py first")
        return

    print("📊 Generating charts...")

    search_results = load_json(search_results_path)
    topic_analysis = load_json(topic_analysis_path)

    generate_html_report(search_results, topic_analysis, str(output_path))

    print(f"\n🎉 Done! Open the HTML file in your browser:")
    print(f"   {output_path}")


if __name__ == "__main__":
    main()
