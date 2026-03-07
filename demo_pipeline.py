"""
Demo script: runs the full pipeline end-to-end with real APIs.

Discovery (GitHub) → Storage (local SQLite) → Summarization (Anthropic) →
Delivery (Telegram). Produces a real Telegram message.

Usage:
    py demo_pipeline.py          (from project root, with .env filled in)
"""

import io
import os
import sys
import logging
from datetime import date
from pathlib import Path
from dotenv import load_dotenv

# Fix Windows console encoding for emoji output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add src/ to path so modules resolve
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Load .env before anything reads env vars
load_dotenv(Path(__file__).parent / ".env")

from discovery import discover_repos, CategoryConfig, RankingCriteria
from storage import init as storage_init, close as storage_close, save_repo, save_summary
from summarization import generate_deep_dive, generate_quick_hit, LLMConfig
from delivery import send_digest, Digest, SummaryWithRepo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("demo")


def main():
    # ── 1. Config ──────────────────────────────────────────────────────
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")
    github_token = os.environ.get("GITHUB_TOKEN") or None

    missing = []
    if not anthropic_key:
        missing.append("ANTHROPIC_API_KEY")
    if not bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not channel_id:
        missing.append("TELEGRAM_CHANNEL_ID")
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Fill them in .env and re-run.")
        sys.exit(1)

    category = CategoryConfig(
        name="agentic-coding",
        description="AI-powered coding tools and agents",
        topics=["ai-coding-agent", "ai-coding-assistant"],
        keywords=["agentic coding"],
        min_stars=100,
        min_readme_length=200,
    )

    ranking = RankingCriteria.STARS

    llm_config = LLMConfig(
        provider="anthropic",
        api_key=anthropic_key,
        deep_dive_model="claude-sonnet-4-6",
        quick_hit_model="claude-haiku-4-5-20251001",
    )

    # ── 2. Discovery ───────────────────────────────────────────────────
    log.info("=== DISCOVERY ===")
    log.info("Category: %s | Ranking: %s", category.name, ranking.value)

    repos = discover_repos(category, ranking, limit=10, token=github_token)
    log.info("Discovered %d repos:", len(repos))
    for i, r in enumerate(repos, 1):
        stars = r.source_metadata.get("stars", 0)
        lang = r.source_metadata.get("primary_language", "?")
        readme_len = len(r.raw_content)
        print(f"  {i:2d}. {r.name:<40s} ⭐{stars:<8,d} 📝{readme_len:,d} chars  [{lang}]")

    # ── 3. Storage ─────────────────────────────────────────────────────
    log.info("=== STORAGE ===")
    db_path = str(Path(__file__).parent / "data" / "demo.db")
    os.makedirs(Path(db_path).parent, exist_ok=True)
    storage_init({"engine": "sqlite", "database": db_path})
    log.info("SQLite database: %s", db_path)

    saved = []
    for r in repos:
        record = save_repo(r)
        saved.append(record)
    log.info("Saved %d repos to database", len(saved))

    # Pick top 1 for deep dive, next 3 for quick hits
    deep_repo = saved[0]
    quick_repos = saved[1:4]

    log.info("Deep dive: %s (⭐%s)", deep_repo.name, deep_repo.source_metadata.get("stars"))
    for i, r in enumerate(quick_repos, 1):
        log.info("Quick hit %d: %s (⭐%s)", i, r.name, r.source_metadata.get("stars"))

    # ── 4. Summarization ───────────────────────────────────────────────
    log.info("=== SUMMARIZATION ===")

    log.info("Generating deep dive for %s (model: %s)...", deep_repo.name, llm_config.deep_dive_model)
    deep_result = generate_deep_dive(deep_repo, llm_config, recent_context=None)
    log.info("Deep dive: %d chars, %s tokens in / %s tokens out",
             len(deep_result.content),
             deep_result.token_usage.get("input_tokens", "?"),
             deep_result.token_usage.get("output_tokens", "?"))
    print(f"\n--- Deep Dive Preview (first 300 chars) ---\n{deep_result.content[:300]}...\n")

    # Save deep dive summary
    deep_summary_record = save_summary(deep_repo.id, "deep", deep_result.content, deep_result.model_used)

    quick_results = []
    for r in quick_repos:
        log.info("Generating quick hit for %s (model: %s)...", r.name, llm_config.quick_hit_model)
        try:
            qr = generate_quick_hit(r, llm_config)
            quick_results.append((r, qr))
            log.info("Quick hit: %d chars", len(qr.content))
            print(f"  → {r.name}: {qr.content[:120]}...")
            save_summary(r.id, "quick", qr.content, qr.model_used)
        except Exception as e:
            log.warning("Quick hit failed for %s: %s", r.name, e)

    # ── 5. Digest Assembly ─────────────────────────────────────────────
    log.info("=== DIGEST ASSEMBLY ===")

    deep_dive_summary = SummaryWithRepo(
        summary_content=deep_result.content,
        repo_name=deep_repo.name,
        repo_url=deep_repo.url,
        stars=deep_repo.source_metadata.get("stars", 0),
        created_at=deep_repo.source_metadata.get("created_at", ""),
    )

    quick_hit_summaries = [
        SummaryWithRepo(
            summary_content=qr.content,
            repo_name=r.name,
            repo_url=r.url,
            stars=r.source_metadata.get("stars", 0),
            created_at=r.source_metadata.get("created_at", ""),
        )
        for r, qr in quick_results
    ]

    digest = Digest(
        deep_dive=deep_dive_summary,
        quick_hits=quick_hit_summaries,
        ranking_criteria=ranking.value,
        date=date.today(),
    )

    log.info("Digest: 1 deep dive + %d quick hits", len(digest.quick_hits))

    # ── 6. Delivery ────────────────────────────────────────────────────
    log.info("=== DELIVERY ===")
    log.info("Sending to Telegram (channel: %s)...", channel_id)

    result = send_digest(digest, channel_id, bot_token)

    if result.success:
        log.info("✅ Delivered! Message ID: %s", result.message_id)
    else:
        log.error("❌ Delivery failed: %s", result.error)

    # ── 7. Cleanup ─────────────────────────────────────────────────────
    storage_close()

    # ── Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print(f"  Repos discovered:   {len(repos)}")
    print(f"  Deep dive:          {deep_repo.name}")
    print(f"  Quick hits:         {len(quick_results)}")
    print(f"  Telegram delivery:  {'✅ Success' if result.success else '❌ Failed: ' + str(result.error)}")
    print(f"  SQLite database:    {db_path}")
    print(f"  Deep dive model:    {deep_result.model_used}")
    if quick_results:
        print(f"  Quick hit model:    {quick_results[0][1].model_used}")
    total_in = deep_result.token_usage.get("input_tokens", 0)
    total_out = deep_result.token_usage.get("output_tokens", 0)
    for _, qr in quick_results:
        total_in += qr.token_usage.get("input_tokens", 0)
        total_out += qr.token_usage.get("output_tokens", 0)
    print(f"  Total tokens:       {total_in:,d} in / {total_out:,d} out")


if __name__ == "__main__":
    main()
