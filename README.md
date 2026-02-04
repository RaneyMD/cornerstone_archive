# The Cornerstone Archive

A digital preservation project digitizing and organizing American architecture and engineering publications from 1850–1920 into a searchable, publicly accessible knowledge base.

## Quick Links

- **Public Wiki:** https://wiki.cornerstonearchive.com
- **Operations Console:** https://console.raneyworld.com (authenticated)
- **Development Wiki:** https://dev.raneyworld.com
- **Development Console:** https://dev-console.raneyworld.com

## About the Project

The Cornerstone Archive preserves and catalogs American architectural and engineering trade journals from the late 19th and early 20th centuries. These publications document the practical knowledge, standards, and innovations that shaped American construction and infrastructure during a transformative period.

**Publications included:**
- American Architect & Building News
- Building Age / American Builder
- Railway Engineering & Other Subjects
- And others from the 1850–1920 period

The archive makes this foundational knowledge publicly accessible through a MediaWiki knowledge base, enabling researchers, historians, and AI-assisted tools to explore and learn from historical construction practices and architectural thinking.

## Repository Contents

This repository contains **code, configuration templates, database migrations, and documentation**. It does **not** store corpus data (JP2/PDF files) or authoritative media files, which are maintained on network storage.

### What's Included

- **`scripts/`** — Python processing scripts for all pipeline stages
- **`config/`** — Configuration templates (never commit actual configs with credentials)
- **`database/`** — SQL migrations for schema evolution
- **`web_console/`** — PHP operations interface for task management
- **`mcps/`** — Model Context Protocol servers for Claude Code integration
- **`policies/`** — Governance documents (quality, release, retention, terminology)
- **`docs/`** — Architecture, development, and operational documentation
- **`tests/`** — Unit, integration, and end-to-end tests

### What's NOT Included

- Raw downloads (JP2/PDF/OCR files from Internet Archive)
- Working-layer intermediates (extracted pages, OCR outputs, segmentation artifacts)
- Reference library masters
- Logs, caches, or database dumps
- Live configuration files with credentials

## System Architecture

### Components

- **OrionMX / OrionMega** — Windows processing computers (not remotely accessible)
- **RaneyHQ (NAS)** — Authoritative storage + workflow hub (SMB shares)
- **HostGator MySQL** — State and metadata database
- **HostGator MediaWiki** — Public knowledge base
- **GitHub** — Version control for code and documentation

### Data Flow

```
Internet Archive
       ↓
[Stage 1: Acquire]  ← Fetch from IA, validate metadata
       ↓
[Stage 2: Extract]  ← Extract pages, OCR, segment articles
       ↓
[Stage 3: Dedupe]   ← Identify and merge duplicate articles
       ↓
[Stage 4: Publish]  ← Export to MediaWiki knowledge base
       ↓
Public Wiki (wiki.cornerstonearchive.com)
```

### Four-Layer Model

1. **Raw Layer** — Original JP2, PDF, OCR files from Internet Archive (read-only, authoritative)
2. **Working Layer** — Intermediate artifacts during processing (temporary, regenerable)
3. **Reference Layer** — Curated reference materials for human consultation
4. **Published Layer** — Final MediaWiki articles, public-facing knowledge base

## Getting Started

### Prerequisites

- Python 3.10+
- MySQL client (HostGator account)
- Access to RaneyHQ NAS
- Git

### Local Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/RaneyMD/cornerstone_archive.git
   cd cornerstone_archive
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Create configuration:**
   ```bash
   cp config/config.example.yaml config/config.yaml
   # Edit config/config.yaml with your environment
   cp config/env.example .env
   # Add credentials to .env (never commit this file)
   ```

4. **Run tests:**
   ```bash
   pytest
   ```

### Development Workflow

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Write tests first (see `tests/README.md`)
3. Implement the feature
4. Run tests locally: `pytest`
5. Commit with clear message: `git commit -m "feat(stage): description"`
6. Push and create a pull request

See `docs/DEVELOPMENT.md` for detailed workflow instructions.

## Documentation

Start with these documents in this order:

1. **`IMPLEMENTATION_ROADMAP.md`** — Full architecture, timeline, and design decisions
2. **`docs/DEVELOPMENT.md`** — How to set up and work with the codebase locally
3. **`docs/DATABASE_SCHEMA.md`** — Database structure and relationships
4. **`docs/WATCHER_SYSTEM.md`** — Task orchestration and processing details
5. **`docs/NAS_LAYOUT.md`** — Network storage structure and conventions
6. **`policies/`** — Quality standards, release criteria, retention policies

## Project Status

### Current Stage

**Stage 0: Foundation** ✓ Complete
- Infrastructure set up (databases, subdomains, SSL)
- Repository structure established
- Testing framework configured

**Stage 1: Internet Archive Acquisition** — In Progress
- Fetch metadata and containers from Internet Archive
- Validate publication information
- Register in database

**Stage 2: Page Extraction & OCR** — Planned
- Extract JP2 files to JPEG
- Copy OCR payloads
- Create page packs with manifests

**Stage 3: Deduplication** — Planned
- Identify duplicate articles across issues
- Merge and canonicalize

**Stage 4: Publication** — Planned
- Generate wikitext
- Publish to MediaWiki
- Create public knowledge base

### Timeline

- **Week 1:** Infrastructure and foundation ✓
- **Week 2–3:** Watcher and core scripts
- **Week 4:** Console and operations interface
- **Week 5–6:** Stage 2 implementation
- **Week 7–8:** Testing and documentation
- **Week 9+:** Production ready

## Contributing

This is currently a single-person project. If you're interested in contributing:

1. Read `docs/DEVELOPMENT.md`
2. Read `policies/` for governance standards
3. Follow the development workflow above
4. Ensure all tests pass before submitting PRs

## License

MIT License — See LICENSE file for details

## Project Lead

**Michael Raney**

## Questions?

- See `docs/TROUBLESHOOTING.md` for common issues
- Check `IMPLEMENTATION_ROADMAP.md` for architectural questions
- Review `docs/` directory for specific topics

---

**Last Updated:** 4 February 2026  
**Repository:** https://github.com/RaneyMD/cornerstone_archive
