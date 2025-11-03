"""
Agents module: AI-powered editorial brain.
Multi-agent system for trend detection, script writing, visual planning, SEO, and quality review.

Agents ONLY read from core and produce structured outputs.
NO side effects (no file I/O, no API calls to external services).

Available agents:
- EditorialStrategist: AI-driven strategic decision-making for content
- DurationStrategist: AI-driven duration optimization for monetization (NEW)
- NarrativeArchitect: AI-driven emotional storytelling for retention (NEW)
- TrendHunter: Selects best video topic from trending candidates
- ScriptWriter: Generates engaging scripts with hooks and CTAs
- VisualPlanner: Creates scene-by-scene visual plans for Veo
- SeoManager: Optimizes titles, descriptions, tags, and thumbnails
- QualityReviewer: Final quality control and compliance verification
- MonetizationQA: AI-driven YouTube monetization readiness validation (NEW)
"""

from yt_autopilot.agents.editorial_strategist import decide_editorial_strategy
from yt_autopilot.agents.duration_strategist import analyze_duration_strategy
from yt_autopilot.agents.narrative_architect import design_narrative_arc
from yt_autopilot.agents.trend_hunter import generate_video_plan
from yt_autopilot.agents.script_writer import write_script
from yt_autopilot.agents.visual_planner import generate_visual_plan
from yt_autopilot.agents.seo_manager import generate_publishing_package
from yt_autopilot.agents.quality_reviewer import review
from yt_autopilot.agents.monetization_qa import validate_monetization_readiness

__all__ = [
    "decide_editorial_strategy",    # EditorialStrategist
    "analyze_duration_strategy",    # DurationStrategist (NEW)
    "design_narrative_arc",         # NarrativeArchitect (NEW)
    "generate_video_plan",          # TrendHunter
    "write_script",                 # ScriptWriter
    "generate_visual_plan",         # VisualPlanner
    "generate_publishing_package",  # SeoManager
    "review",                       # QualityReviewer
    "validate_monetization_readiness",  # MonetizationQA (NEW)
]
