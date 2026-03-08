#!/usr/bin/env python3
"""Daily pipeline entry point for cron."""

import io
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent / "src"))

load_dotenv(Path(__file__).parent / ".env")

from discovery.types import CategoryConfig
from orchestrator import run_daily_pipeline, PipelineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "data" / "pipeline.log"),
        logging.StreamHandler(),
    ],
)


def main():
    config = PipelineConfig(
        category=CategoryConfig(
            name="agentic-coding",
            description="AI-powered coding tools and agents",
            topics=["ai-coding-agent", "ai-coding-assistant"],
            keywords=["agentic coding"],
            expansion_topics=["llm-agent", "code-generation"],
            min_stars=100,
            min_readme_length=200,
        ),
        channel_id="@github_discovery",
        discovery_limit=20,
    )

    result = run_daily_pipeline(config)

    if result.success:
        logging.info(
            "Pipeline succeeded: %d repos, %d summaries",
            result.repos_discovered,
            result.summaries_generated,
        )
    else:
        logging.error("Pipeline failed: %s", result.errors)
        sys.exit(1)


if __name__ == "__main__":
    main()
