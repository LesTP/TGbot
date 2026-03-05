# TGBot

## Framework
This project follows the From Idea to Code governance framework.

## Always Loaded
- @PROJECT.md — scope, audience, constraints
- @ARCHITECTURE.md — component map, data flow, sequence
- @GOVERNANCE.md — development process reference

## Load for Current Module
Load the relevant files when starting work on a specific module:
- ARCH_[module].md — module contract and interface spec
- DEVPLAN.md — current status, phase plan, cold start summary
- DEVLOG.md — history (load when debugging or reviewing)

## Available Modules
- Discovery — find repos on GitHub matching category criteria, apply quality filters, rank results
- Summarization — take a discovered repo, generate deep dive or quick hit summary via LLM, extract structured metadata
- Delivery — format a digest message, send it to Telegram
- Storage — persist repos, summaries, feature history; answer queries like "was this repo featured recently?"
- Orchestrator — coordinate the daily pipeline: discover → filter already-featured → summarize → deliver

## Project-Specific Notes
