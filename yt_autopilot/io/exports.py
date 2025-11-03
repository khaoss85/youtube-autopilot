"""
Exports Module: Export data to various formats for analysis.

This module handles exporting datastore data to CSV, Excel, or other
formats for external analysis and reporting.

Phase 1 Refactor: Added Markdown export for content packages.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
from yt_autopilot.core.config import get_config
from yt_autopilot.core.logger import logger
from yt_autopilot.core.schemas import ContentPackage
from yt_autopilot.io.datastore import list_published_videos, get_metrics_history


def export_report_csv(csv_path: Optional[str] = None) -> str:
    """
    Exports video performance report to CSV.

    Creates a CSV file with columns:
    - youtube_video_id: YouTube video ID
    - title: Video title
    - publish_at: Scheduled/actual publish time
    - views_latest: Most recent view count
    - ctr_latest: Most recent click-through rate
    - avg_view_duration_latest: Most recent average view duration
    - watch_time_latest: Most recent total watch time

    Args:
        csv_path: Optional custom path for CSV file.
                  If None, uses ./data/report.csv

    Returns:
        Path to generated CSV file

    Example:
        >>> report_path = export_report_csv()
        >>> print(f"Report saved to: {report_path}")
        Report saved to: ./data/report.csv
    """
    logger.info("Exporting performance report to CSV...")

    if csv_path is None:
        config = get_config()
        data_dir = config["PROJECT_ROOT"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = str(data_dir / "report.csv")

    # Get all published videos
    videos = list_published_videos()

    if not videos:
        logger.warning("No videos found in datastore - creating empty report")

    # Prepare report data
    report_rows: List[Dict[str, Any]] = []

    for video in videos:
        video_id = video["youtube_video_id"]

        # Get latest metrics for this video
        metrics_history = get_metrics_history(video_id)

        if metrics_history:
            latest_metrics = metrics_history[-1]  # Most recent
            views = latest_metrics.views
            ctr = latest_metrics.ctr
            avg_duration = latest_metrics.average_view_duration_seconds
            watch_time = latest_metrics.watch_time_seconds
        else:
            # No metrics yet
            views = 0
            ctr = 0.0
            avg_duration = 0.0
            watch_time = 0.0

        report_rows.append({
            "youtube_video_id": video_id,
            "title": video["title"],
            "publish_at": video["publish_at"],
            "status": video["status"],
            "views_latest": views,
            "ctr_latest": f"{ctr:.4f}",
            "avg_view_duration_latest": f"{avg_duration:.2f}",
            "watch_time_latest": f"{watch_time:.2f}"
        })

    # Write CSV
    if report_rows:
        fieldnames = [
            "youtube_video_id",
            "title",
            "publish_at",
            "status",
            "views_latest",
            "ctr_latest",
            "avg_view_duration_latest",
            "watch_time_latest"
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(report_rows)

        logger.info(f"✓ Report exported to {csv_path}")
        logger.info(f"  Videos: {len(report_rows)}")
        logger.info(f"  Columns: {len(fieldnames)}")
    else:
        # Create empty CSV with headers
        fieldnames = [
            "youtube_video_id",
            "title",
            "publish_at",
            "status",
            "views_latest",
            "ctr_latest",
            "avg_view_duration_latest",
            "watch_time_latest"
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

        logger.info(f"✓ Empty report created at {csv_path}")

    return csv_path


def export_metrics_timeseries_csv(video_id: str, csv_path: Optional[str] = None) -> str:
    """
    Exports time-series metrics for a specific video to CSV.

    Args:
        video_id: YouTube video ID
        csv_path: Optional custom path for CSV file

    Returns:
        Path to generated CSV file

    Example:
        >>> path = export_metrics_timeseries_csv("abc123")
        >>> print(f"Timeseries saved to: {path}")
        Timeseries saved to: ./data/metrics_abc123.csv
    """
    logger.info(f"Exporting metrics timeseries for video {video_id}...")

    if csv_path is None:
        config = get_config()
        data_dir = config["PROJECT_ROOT"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = str(data_dir / f"metrics_{video_id}.csv")

    # Get metrics history
    metrics_history = get_metrics_history(video_id)

    if not metrics_history:
        logger.warning(f"No metrics found for video {video_id}")
        return csv_path

    # Write CSV
    fieldnames = [
        "collected_at",
        "views",
        "watch_time_seconds",
        "average_view_duration_seconds",
        "ctr"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for metrics in metrics_history:
            writer.writerow({
                "collected_at": metrics.collected_at_iso,
                "views": metrics.views,
                "watch_time_seconds": f"{metrics.watch_time_seconds:.2f}",
                "average_view_duration_seconds": f"{metrics.average_view_duration_seconds:.2f}",
                "ctr": f"{metrics.ctr:.4f}"
            })

    logger.info(f"✓ Timeseries exported to {csv_path}")
    logger.info(f"  Data points: {len(metrics_history)}")

    return csv_path


# ==============================================================================
# Phase 1 Refactor: Markdown Export for Content Packages
# ==============================================================================

def export_content_package_to_markdown(
    content_package: ContentPackage,
    script_internal_id: str,
    workspace_config: Dict[str, Any],
    output_dir: Optional[Path] = None
) -> str:
    """
    Exports a ContentPackage to professional Markdown format.

    Phase 1 Refactor: Creates human-readable script with AI-ready scene prompts.

    Output includes:
    - Overview: Title, duration, editorial strategy, brand context
    - Full script: Complete voiceover text
    - Scene breakdown: Human-readable + AI tool prompts (copy-paste ready)
    - SEO metadata: Title, description, tags, hashtags

    Args:
        content_package: ContentPackage to export
        script_internal_id: Unique identifier for this script
        workspace_config: Workspace configuration (brand_tone, visual_style, etc.)
        output_dir: Optional custom output directory (default: output/{workspace_id}/{script_id}/)

    Returns:
        Path to generated Markdown file

    Example:
        >>> from yt_autopilot.core.workspace_manager import load_workspace_config
        >>> workspace = load_workspace_config("finance")
        >>> path = export_content_package_to_markdown(package, "abc123", workspace)
        >>> print(f"Exported to: {path}")
        Exported to: output/finance/abc123/content_package.md
    """
    logger.info(f"Exporting ContentPackage to Markdown: {script_internal_id}")

    # Determine output directory
    if output_dir is None:
        config = get_config()
        workspace_id = workspace_config.get("workspace_id", "default")
        output_dir = config["OUTPUT_DIR"] / workspace_id / script_internal_id

    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "content_package.md"

    # Extract data
    video_plan = content_package.video_plan
    script = content_package.script
    visuals = content_package.visuals
    publishing = content_package.publishing
    editorial_decision = content_package.editorial_decision

    # Calculate total duration
    total_duration = sum(scene.est_duration_seconds for scene in visuals.scenes)

    # Get brand context
    brand_tone = workspace_config.get("brand_tone", "Not specified")
    visual_style = workspace_config.get("visual_style", "Not specified")
    vertical_id = workspace_config.get("vertical_id", "general")

    # Build Markdown content
    markdown_lines = []

    # Header
    markdown_lines.append(f"# {publishing.final_title}")
    markdown_lines.append("")
    markdown_lines.append(f"**Script ID**: `{script_internal_id}`  ")
    markdown_lines.append(f"**Workspace**: {workspace_config.get('workspace_name', 'Unknown')} ({vertical_id})  ")
    markdown_lines.append(f"**Status**: {content_package.status}")
    markdown_lines.append("")
    markdown_lines.append("---")
    markdown_lines.append("")

    # OVERVIEW Section
    markdown_lines.append("## 📋 OVERVIEW")
    markdown_lines.append("")
    markdown_lines.append(f"**Duration**: {total_duration}s  ")
    markdown_lines.append(f"**Series**: {video_plan.series_id or 'N/A'}  ")

    if editorial_decision:
        markdown_lines.append(f"**Serie**: {editorial_decision.serie_concept}  ")
        markdown_lines.append(f"**Angle**: {editorial_decision.angle}  ")
        markdown_lines.append(f"**Monetization**: {editorial_decision.monetization_path}  ")
        markdown_lines.append("")
        markdown_lines.append("### Editorial Strategy (AI-Driven)")
        markdown_lines.append(f"> {editorial_decision.reasoning_summary}")
        markdown_lines.append("")

    markdown_lines.append("### Brand Context")
    markdown_lines.append(f"**Brand Tone**: {brand_tone}")
    markdown_lines.append("")
    markdown_lines.append(f"**Visual Style**: {visual_style}")
    markdown_lines.append("")

    # AI Decision Rationale Section
    if any([
        package.duration_strategy_reasoning,
        package.format_reconciliation_reasoning,
        package.narrative_design_reasoning,
        package.cta_strategy_reasoning
    ]):
        markdown_lines.append("### AI Decision Rationale")
        markdown_lines.append("")
        markdown_lines.append("*Why did the AI make these specific choices? Here's the reasoning behind key decisions:*")
        markdown_lines.append("")

        if package.duration_strategy_reasoning:
            markdown_lines.append("**Duration Strategy**")
            markdown_lines.append(f"> {package.duration_strategy_reasoning}")
            markdown_lines.append("")

        if package.format_reconciliation_reasoning:
            markdown_lines.append("**Format Reconciliation**")
            markdown_lines.append(f"> {package.format_reconciliation_reasoning}")
            markdown_lines.append("")

        if package.narrative_design_reasoning:
            markdown_lines.append("**Narrative Design**")
            markdown_lines.append(f"> {package.narrative_design_reasoning}")
            markdown_lines.append("")

        if package.cta_strategy_reasoning:
            markdown_lines.append("**CTA Strategy**")
            markdown_lines.append(f"> {package.cta_strategy_reasoning}")
            markdown_lines.append("")

    # Full Script
    markdown_lines.append("### Full Script")
    markdown_lines.append("```")
    markdown_lines.append(script.full_voiceover_text)
    markdown_lines.append("```")
    markdown_lines.append("")
    markdown_lines.append("---")
    markdown_lines.append("")

    # SCENE BREAKDOWN Section
    markdown_lines.append("## 🎬 SCENE BREAKDOWN")
    markdown_lines.append("")
    markdown_lines.append("*Copy the AI prompts below and paste them into your preferred video generation tool (RunwayML, Luma, Pika, etc.)*")
    markdown_lines.append("")

    for scene in visuals.scenes:
        scene_id = scene.scene_id
        segment_type = scene.segment_type or "content"
        duration = scene.est_duration_seconds
        voiceover = scene.voiceover_text
        ai_prompt_base = scene.prompt_for_ai_tool

        # Scene header
        markdown_lines.append(f"### Scene {scene_id}: {segment_type.title()} ({duration}s)")
        markdown_lines.append("")

        # Human-readable section
        markdown_lines.append("**Voiceover**:")
        markdown_lines.append(f"> \"{voiceover}\"")
        markdown_lines.append("")

        # Reference image
        markdown_lines.append("**Reference Image**:")
        if scene.reference_image_path:
            # Image exists - show it embedded
            markdown_lines.append(f"![Scene {scene_id} Reference]({scene.reference_image_path})")
            markdown_lines.append("")
        else:
            # Image not generated yet - show placeholder
            markdown_lines.append(f"*[Generate with: `python run.py review export-visual-deck {script_internal_id}`]*")
            markdown_lines.append("")

        # AI-ready prompt section
        markdown_lines.append("**AI Video Prompt** *(copy-paste ready)*:")
        markdown_lines.append("```")

        # Build comprehensive AI prompt
        ai_prompt_full = f"{ai_prompt_base}\n\n"
        ai_prompt_full += f"Technical Specs:\n"
        ai_prompt_full += f"- Aspect ratio: 9:16 (vertical format for YouTube Shorts)\n"
        ai_prompt_full += f"- Duration: {duration} seconds\n"
        ai_prompt_full += f"- Style: {visual_style[:150] if len(visual_style) > 150 else visual_style}\n"
        ai_prompt_full += f"\n"
        ai_prompt_full += f"Audio Context:\n"
        ai_prompt_full += f"During this scene, the voiceover says: \"{voiceover}\"\n"

        # Add continuity note if not first scene
        if scene_id > 0:
            ai_prompt_full += f"\n"
            ai_prompt_full += f"Continuity Note:\n"
            ai_prompt_full += f"This scene should maintain visual coherence with the previous scene.\n"

        markdown_lines.append(ai_prompt_full)
        markdown_lines.append("```")
        markdown_lines.append("")
        markdown_lines.append("---")
        markdown_lines.append("")

    # SEO METADATA Section
    markdown_lines.append("## 🎯 SEO METADATA")
    markdown_lines.append("")
    markdown_lines.append("### Title")
    markdown_lines.append(f"```")
    markdown_lines.append(publishing.final_title)
    markdown_lines.append("```")
    markdown_lines.append("")

    markdown_lines.append("### Description")
    markdown_lines.append("```")
    markdown_lines.append(publishing.description)
    markdown_lines.append("```")
    markdown_lines.append("")

    markdown_lines.append("### Tags")
    markdown_lines.append("```")
    markdown_lines.append(", ".join(publishing.tags))
    markdown_lines.append("```")
    markdown_lines.append("")

    # Write to file
    markdown_content = "\n".join(markdown_lines)
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    logger.info(f"✓ Markdown exported to {markdown_path}")
    logger.info(f"  Scenes: {len(visuals.scenes)}")
    logger.info(f"  Total duration: {total_duration}s")

    return str(markdown_path)
