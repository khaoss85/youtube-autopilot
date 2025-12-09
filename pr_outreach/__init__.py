"""
PR Outreach Module - Media PR Outreach Automation

This module extends youtube-autopilot with capabilities for automated
media PR outreach campaigns. It enables:

- Article discovery for product placement opportunities
- Author research and contact validation
- Personalized email generation with human-like behavior
- Quality validation (spam check, personalization scoring)
- Human approval workflow
- Email sending and response tracking

Architecture mirrors youtube-autopilot:
- core/: Schemas and shared utilities
- agents/: AI-driven agents (ArticleHunter, EmailWriter, etc.)
- services/: External integrations (scraping, email APIs)
- pipeline/: Orchestration (build_outreach_package)
- io/: Persistence (outreach_datastore)
"""

__version__ = "0.1.0"
