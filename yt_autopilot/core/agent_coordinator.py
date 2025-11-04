"""
Agent Coordinator - Centralized Orchestration for All Agents

This module provides a unified framework for orchestrating all agents in the
YouTube Autopilot pipeline. It replaces hardcoded agent sequences with a
flexible, AI-driven orchestration system.

Key Features:
- Unified context propagation (AgentContext)
- Standardized error handling and retry logic
- Performance tracking and analytics
- Support for both linear (backward compatible) and AI-driven orchestration
- Zero changes required to existing agents (adapter layer)

Architecture:
    AgentCoordinator (Main orchestrator)
        ↓
    AgentRegistry (12 agents registered with metadata)
        ↓
    AgentContext (Unified state object)
        ↓
    Linear Mode OR AI-Driven Mode (future)

Author: YT Autopilot Team
Version: 1.0 (Phase A4)
Date: 2025-11-02
"""

from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import logging
import uuid

from yt_autopilot.core.schemas import (
    VideoPlan,
    TrendCandidate,
    VideoScript,
    EditorialDecision,
    Timeline
)
from yt_autopilot.core.logger import logger

# Forward declarations for type hints (actual imports happen in AgentRegistry)
VisualPlan = Any  # Will be imported from visual_planner
PublishingPackage = Any  # Will be imported from seo_manager
ContentPackage = Any  # Will be from build_video_package
ValidationResult = Any  # Will be from pipeline_validator


# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass
class AgentCallRecord:
    """
    Record of a single agent call.
    Tracks performance and execution metadata.
    """
    agent_name: str
    started_at: float  # Unix timestamp
    completed_at: float  # Unix timestamp
    status: str  # "success", "fallback", "failed"
    execution_time_ms: float
    retry_count: int
    error_message: Optional[str] = None


class AgentError(Exception):
    """
    Base error class for all agent failures.

    Provides structured error information for:
    - Error classification (llm_failure, validation_error, timeout, etc.)
    - Recovery hints (is_recoverable, fallback_used)
    - Debugging info (original_error, retry_count)
    """

    def __init__(
        self,
        agent_name: str,
        error_type: str,
        message: str,
        original_error: Optional[Exception] = None,
        retry_count: int = 0,
        is_recoverable: bool = True,
        fallback_used: bool = False
    ):
        super().__init__(message)
        self.agent_name = agent_name
        self.error_type = error_type  # "llm_failure", "validation_error", "timeout", "dependency_error"
        self.message = message
        self.original_error = original_error
        self.retry_count = retry_count
        self.is_recoverable = is_recoverable
        self.fallback_used = fallback_used

    def __str__(self):
        return f"[{self.agent_name}] {self.error_type}: {self.message} (retries: {self.retry_count})"


@dataclass
class AgentResult:
    """
    Standard return type for all agent calls.

    Provides:
    - Execution status (success/fallback/failed)
    - Agent output (any type - Dict, EditorialDecision, VideoScript, etc.)
    - Performance metrics (execution_time_ms, retry_count)
    - Error information (if failed)
    - Agent-specific metadata
    """
    agent_name: str
    status: str  # "success", "fallback", "failed"
    output: Any  # Actual agent output (type varies by agent)
    execution_time_ms: float
    retry_count: int
    error: Optional[AgentError] = None
    metadata: Dict = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        """Check if agent call was successful."""
        return self.status == "success"

    @property
    def used_fallback(self) -> bool:
        """Check if fallback strategy was used."""
        return self.status == "fallback"

    @property
    def failed(self) -> bool:
        """Check if agent call failed completely."""
        return self.status == "failed"


@dataclass
class AgentContext:
    """
    Unified context for all agent calls.

    This replaces inconsistent parameter passing across 12 agents.
    Instead of each agent having different parameters (workspace vs memory,
    topic vs video_plan, etc.), all agents receive this unified context.

    Benefits:
    - Single source of truth for pipeline state
    - Easy to add new context without changing agent signatures
    - Tracing support with execution_id
    - Agent call history for debugging
    - Performance data accumulation

    Usage:
        context = AgentContext(
            workspace=workspace,
            video_plan=video_plan,
            llm_generate_fn=llm_generate_fn,
            workspace_id=workspace_id,
            execution_id=str(uuid.uuid4())
        )

        # Populate as pipeline progresses
        context.editorial_decision = decide_editorial_strategy(...)
        context.duration_strategy = analyze_duration_strategy(...)
        # etc.
    """

    # ============ Core Context (Always Present) ============
    workspace: Dict
    video_plan: VideoPlan
    llm_generate_fn: Callable  # Language-validated wrapper
    workspace_id: str
    execution_id: str  # UUID for tracing multi-agent flow

    # ============ Trend Data ============
    selected_trend: Optional[TrendCandidate] = None
    top_candidates: List[TrendCandidate] = field(default_factory=list)

    # ============ Agent Outputs (Populated as Pipeline Progresses) ============
    editorial_decision: Optional[EditorialDecision] = None
    duration_strategy: Optional[Dict] = None
    reconciled_format: Optional[Timeline] = None  # Phase C - P0: Now Timeline object
    narrative_arc: Optional[Dict] = None
    cta_strategy: Optional[Dict] = None
    content_depth_strategy: Optional[Dict] = None
    script: Optional[VideoScript] = None
    visual_plan: Optional[Any] = None  # VisualPlan
    publishing: Optional[Any] = None  # PublishingPackage
    quality_review: Optional[Dict] = None
    monetization_qa: Optional[Dict] = None

    # ============ Pipeline State ============
    agent_call_history: List[AgentCallRecord] = field(default_factory=list)
    errors: List[AgentError] = field(default_factory=list)
    validation_results: List[Any] = field(default_factory=list)  # List[ValidationResult]

    # ============ Performance & Analytics ============
    performance_history: List[Dict] = field(default_factory=list)
    pipeline_start_time: float = field(default_factory=time.time)

    # ============ Optional Context ============
    memory: Optional[Dict] = None  # For agents that use memory
    series_format: Optional[Dict] = None  # Serie format from YAML
    thresholds: Optional[Dict] = None  # FASE 2.3: Quality validation thresholds

    def get_agent_output(self, agent_name: str) -> Optional[Any]:
        """
        Retrieve output from a specific agent.

        Args:
            agent_name: Name of agent (e.g., "editorial_strategist")

        Returns:
            Agent output if available, None otherwise
        """
        mapping = {
            "editorial_strategist": self.editorial_decision,
            "duration_strategist": self.duration_strategy,
            "format_reconciler": self.reconciled_format,
            "narrative_architect": self.narrative_arc,
            "cta_strategist": self.cta_strategy,
            "content_depth_strategist": self.content_depth_strategy,
            "script_writer": self.script,
            "visual_planner": self.visual_plan,
            "seo_manager": self.publishing,
            "quality_reviewer": self.quality_review,
            "monetization_qa": self.monetization_qa
        }
        return mapping.get(agent_name)

    def set_agent_output(self, agent_name: str, output: Any):
        """
        Store agent output in context.

        Args:
            agent_name: Name of agent
            output: Agent's output (type varies by agent)
        """
        if agent_name == "editorial_strategist":
            self.editorial_decision = output
        elif agent_name == "duration_strategist":
            self.duration_strategy = output
        elif agent_name == "format_reconciler":
            self.reconciled_format = output
        elif agent_name == "narrative_architect":
            self.narrative_arc = output
        elif agent_name == "cta_strategist":
            self.cta_strategy = output
        elif agent_name == "content_depth_strategist":
            self.content_depth_strategy = output
        elif agent_name == "script_writer":
            self.script = output
        elif agent_name == "visual_planner":
            self.visual_plan = output
        elif agent_name == "seo_manager":
            self.publishing = output
        elif agent_name == "quality_reviewer":
            self.quality_review = output
        elif agent_name == "monetization_qa":
            self.monetization_qa = output
        else:
            logger.warning(f"Unknown agent: {agent_name} - cannot store output")

    def get_total_execution_time_ms(self) -> float:
        """Calculate total execution time for all agents."""
        return sum(record.execution_time_ms for record in self.agent_call_history)

    def get_agent_count(self) -> int:
        """Get number of agents called so far."""
        return len(self.agent_call_history)

    def get_error_count(self) -> int:
        """Get number of errors encountered."""
        return len(self.errors)

    def get_fallback_count(self) -> int:
        """Get number of fallback strategies used."""
        return sum(1 for record in self.agent_call_history if record.status == "fallback")


# ============================================================================
# AGENT REGISTRY
# ============================================================================

@dataclass
class AgentSpec:
    """
    Specification for a single agent.

    Defines agent metadata:
    - Function to call
    - Criticality (pipeline stops if critical agent fails)
    - Retry settings
    - Timeout
    - Fallback strategy
    - Dependencies (required prior agents)
    - Quality validation (FASE 1: Quality Retry Framework)

    Example:
        AgentSpec(
            name="editorial_strategist",
            function=decide_editorial_strategy,
            is_critical=True,
            max_retries=2,
            timeout_ms=60000,
            dependencies=[],  # No dependencies
            quality_validator=validate_editorial_coherence,  # FASE 1
            quality_retry_fn=regenerate_editorial_with_fix  # FASE 1
        )
    """
    name: str
    function: Callable
    is_critical: bool  # Pipeline stops if this agent fails (no fallback)
    max_retries: int = 2
    timeout_ms: int = 60000  # 60 seconds default
    fallback_strategy: Optional[Callable] = None
    dependencies: List[str] = field(default_factory=list)  # Required prior agents
    description: str = ""  # Human-readable description

    # FASE 1: Quality Retry Framework
    quality_validator: Optional[Callable] = None  # Validates output quality (not just errors)
    quality_retry_fn: Optional[Callable] = None   # Regenerates output with constraints

    def has_dependencies(self) -> bool:
        """Check if agent has dependencies."""
        return len(self.dependencies) > 0

    def can_run(self, context: 'AgentContext') -> bool:
        """
        Check if agent can run given current context.
        Verifies all dependencies are satisfied.
        """
        for dep in self.dependencies:
            if context.get_agent_output(dep) is None:
                return False
        return True


class AgentRegistry:
    """
    Registry of all available agents.

    Enables:
    - Dynamic agent selection
    - Dependency tracking
    - Metadata lookup
    - Parallel execution discovery

    Usage:
        registry = AgentRegistry()
        spec = registry.get("editorial_strategist")
        runnable_agents = registry.get_runnable_agents(context)
    """

    def __init__(self):
        self.agents: Dict[str, AgentSpec] = {}
        self._register_all_agents()

    def _register_all_agents(self):
        """
        Register all 12 agents from Phase A1-A3.

        Import agents and register with metadata (dependencies, criticality, etc.).
        """
        # Import all agents
        from yt_autopilot.agents.editorial_strategist import decide_editorial_strategy
        from yt_autopilot.agents.duration_strategist import analyze_duration_strategy
        from yt_autopilot.agents.format_reconciler import reconcile_format_strategies
        from yt_autopilot.agents.narrative_architect import design_narrative_arc
        from yt_autopilot.agents.cta_strategist import design_cta_strategy
        from yt_autopilot.agents.content_depth_strategist import analyze_content_depth
        from yt_autopilot.agents.script_writer import write_script
        from yt_autopilot.agents.visual_planner import generate_visual_plan
        from yt_autopilot.agents.seo_manager import generate_publishing_package
        from yt_autopilot.agents.quality_reviewer import review
        from yt_autopilot.agents.monetization_qa import validate_monetization_readiness

        # ===== PHASE 1: Strategic Decision Agents =====

        self.register(AgentSpec(
            name="editorial_strategist",
            function=decide_editorial_strategy,
            is_critical=True,
            max_retries=2,
            timeout_ms=60000,
            dependencies=[],  # No dependencies - can run immediately
            description="Decides video format, angle, duration target, and serie concept based on trend analysis"
        ))

        self.register(AgentSpec(
            name="duration_strategist",
            function=analyze_duration_strategy,
            is_critical=True,
            max_retries=2,
            timeout_ms=60000,
            dependencies=[],  # No dependencies - can run in parallel with editorial
            description="Analyzes optimal video duration for monetization (ads, shorts fund, affiliate, etc.)"
        ))

        # ===== PHASE 2: Format Reconciliation =====

        self.register(AgentSpec(
            name="format_reconciler",
            function=reconcile_format_strategies,
            is_critical=False,  # Optional if divergence small
            max_retries=1,
            timeout_ms=45000,
            dependencies=["editorial_strategist", "duration_strategist"],
            description="Reconciles conflicts between editorial and duration strategies using weight-based resolution"
        ))

        # ===== PHASE 3: Narrative & Content Planning =====

        self.register(AgentSpec(
            name="narrative_architect",
            function=design_narrative_arc,
            is_critical=True,
            max_retries=2,
            timeout_ms=60000,
            dependencies=["editorial_strategist", "duration_strategist"],  # Needs duration for pacing
            description="Designs emotional storytelling arc (Hook → Agitation → Solution → Payoff + CTA)",
            quality_validator=validate_narrative_bullet_count,  # FASE 1.6: Validates bullet count matches Content Depth Strategy
            quality_retry_fn=regenerate_narrative_with_bullet_constraint  # FASE 1.6: Regenerates with explicit bullet constraint
        ))

        self.register(AgentSpec(
            name="cta_strategist",
            function=design_cta_strategy,
            is_critical=True,
            max_retries=2,
            timeout_ms=45000,
            dependencies=["editorial_strategist", "duration_strategist", "narrative_architect"],
            description="Designs strategic CTA placement (mid-roll + outro) based on narrative emotional beats"
        ))

        self.register(AgentSpec(
            name="content_depth_strategist",
            function=analyze_content_depth,
            is_critical=True,
            max_retries=2,
            timeout_ms=45000,
            dependencies=["editorial_strategist", "narrative_architect"],
            description="AI-driven bullets count optimization (no hardcoded values, LLM Chain-of-Thought)"
        ))

        # ===== PHASE 4: Script Generation =====

        self.register(AgentSpec(
            name="script_writer",
            function=write_script,
            is_critical=True,
            max_retries=2,
            timeout_ms=90000,  # Script generation can take longer
            dependencies=[
                "editorial_strategist",
                "narrative_architect",
                "cta_strategist",
                "content_depth_strategist"
            ],
            description="Generates full video script with voiceover, bullets, hook, and outro CTA"
        ))

        # ===== PHASE 5: Visual Planning =====

        self.register(AgentSpec(
            name="visual_planner",
            function=generate_visual_plan,
            is_critical=True,
            max_retries=2,
            timeout_ms=90000,
            dependencies=["script_writer", "duration_strategist"],
            description="Creates visual plan with scenes, Veo prompts, camera movements, and aspect ratio"
        ))

        # ===== PHASE 6: Publishing & SEO =====

        self.register(AgentSpec(
            name="seo_manager",
            function=generate_publishing_package,
            is_critical=True,
            max_retries=2,
            timeout_ms=45000,
            dependencies=["script_writer"],  # Needs script for metadata optimization
            description="Generates SEO-optimized title, description, tags, and thumbnail concept"
        ))

        # ===== PHASE 7: Quality Assurance =====

        self.register(AgentSpec(
            name="quality_reviewer",
            function=review,
            is_critical=False,  # Non-blocking - provides suggestions
            max_retries=1,
            timeout_ms=45000,
            dependencies=["script_writer", "visual_planner"],
            description="Reviews content quality and provides improvement suggestions"
        ))

        self.register(AgentSpec(
            name="monetization_qa",
            function=validate_monetization_readiness,
            is_critical=True,  # Critical - ensures monetization compliance
            max_retries=2,
            timeout_ms=60000,
            dependencies=["duration_strategist", "narrative_architect", "script_writer"],
            description="Validates monetization readiness (duration, format, content depth, CTA strategy)"
        ))

        logger.info(f"AgentRegistry initialized with {len(self.agents)} agents")

    def register(self, spec: AgentSpec):
        """Register an agent."""
        self.agents[spec.name] = spec
        logger.debug(f"Registered agent: {spec.name} (critical={spec.is_critical}, deps={spec.dependencies})")

    def get(self, agent_name: str) -> Optional[AgentSpec]:
        """Get agent spec by name."""
        return self.agents.get(agent_name)

    def get_all(self) -> List[AgentSpec]:
        """Get all registered agents."""
        return list(self.agents.values())

    def get_runnable_agents(self, context: AgentContext) -> List[str]:
        """
        Get agents that can run given current context.

        Checks:
        1. Agent hasn't already run
        2. All dependencies are satisfied

        Returns:
            List of agent names that can run
        """
        runnable = []
        for name, spec in self.agents.items():
            # Check if agent already ran
            if context.get_agent_output(name) is not None:
                continue

            # Check dependencies
            if spec.can_run(context):
                runnable.append(name)

        return runnable

    def get_critical_agents(self) -> List[str]:
        """Get names of all critical agents."""
        return [name for name, spec in self.agents.items() if spec.is_critical]

    def get_agent_dependencies(self, agent_name: str) -> List[str]:
        """Get dependencies for a specific agent."""
        spec = self.get(agent_name)
        return spec.dependencies if spec else []


# ============================================================================
# AGENT COORDINATOR
# ============================================================================

class AgentCoordinator:
    """
    Centralized orchestrator for all agent calls.

    Features:
    - Unified context propagation (AgentContext)
    - Standardized error handling with retry logic
    - Performance tracking and analytics
    - Support for linear (backward compatible) execution mode
    - Zero changes required to existing agents (adapter layer)

    Usage:
        # Initialize
        coordinator = AgentCoordinator()

        # Create context
        context = AgentContext(
            workspace=workspace,
            video_plan=video_plan,
            llm_generate_fn=llm_generate_fn,
            workspace_id=workspace_id,
            execution_id=str(uuid.uuid4())
        )

        # Execute pipeline
        package = coordinator.execute_pipeline(context, mode="linear")

        # Or call individual agents
        result = coordinator.call_agent("editorial_strategist", context)
    """

    def __init__(self, registry: Optional[AgentRegistry] = None):
        """
        Initialize AgentCoordinator.

        Args:
            registry: Optional AgentRegistry (creates default if not provided)
        """
        self.registry = registry or AgentRegistry()
        logger.info("AgentCoordinator initialized")

    def call_agent(
        self,
        agent_name: str,
        context: AgentContext,
        max_retries: Optional[int] = None
    ) -> AgentResult:
        """
        Call single agent with retry logic and error handling.

        Features:
        - Automatic retry on transient errors (LLM timeouts, rate limits)
        - Fallback strategy on persistent errors
        - Performance tracking (execution time per attempt)
        - Error accumulation for analytics
        - Context adaptation (no agent changes required)

        Args:
            agent_name: Name of agent to call (e.g., "editorial_strategist")
            context: Current AgentContext with all pipeline state
            max_retries: Override default retry count (None = use agent spec)

        Returns:
            AgentResult with status ("success", "fallback", "failed"),
            output, execution time, and error info

        Example:
            result = coordinator.call_agent("editorial_strategist", context)
            if result.is_success:
                context.editorial_decision = result.output
        """
        spec = self.registry.get(agent_name)
        if not spec:
            raise ValueError(f"Unknown agent: {agent_name}")

        retries = max_retries if max_retries is not None else spec.max_retries

        logger.info(f"{'=' * 70}")
        logger.info(f"CALLING AGENT: {agent_name}")
        logger.info(f"  Max retries: {retries}")
        logger.info(f"  Critical: {spec.is_critical}")
        logger.info(f"  Dependencies: {spec.dependencies}")
        logger.info(f"{'=' * 70}")

        # Check dependencies
        if spec.has_dependencies():
            for dep in spec.dependencies:
                if context.get_agent_output(dep) is None:
                    error_msg = f"Dependency not satisfied: {dep} output missing"
                    logger.error(f"  ❌ {error_msg}")

                    error = AgentError(
                        agent_name=agent_name,
                        error_type="dependency_error",
                        message=error_msg,
                        retry_count=0,
                        is_recoverable=False
                    )

                    context.errors.append(error)

                    return AgentResult(
                        agent_name=agent_name,
                        status="failed",
                        output=None,
                        execution_time_ms=0,
                        retry_count=0,
                        error=error
                    )

        # Retry loop
        for attempt in range(retries + 1):
            try:
                logger.info(f"  🤖 Attempt {attempt + 1}/{retries + 1}...")

                start_time = time.time()

                # Call agent with context adaptation
                output = self._call_agent_with_adaptation(spec, context)

                execution_time_ms = (time.time() - start_time) * 1000

                # FASE 2.3: Load quality validation thresholds (if not already loaded)
                if spec.quality_validator and context.thresholds is None:
                    from yt_autopilot.core.config import load_validation_thresholds

                    # Extract workspace_id and format_type from context
                    workspace_id = context.workspace_id
                    format_type = None
                    if context.duration_strategy:
                        format_type = context.duration_strategy.get('format_type')

                    try:
                        context.thresholds = load_validation_thresholds(
                            workspace_id=workspace_id,
                            format_type=format_type
                        )
                        logger.debug(f"  Loaded thresholds for workspace={workspace_id}, format={format_type}")
                    except Exception as e:
                        logger.warning(f"  Failed to load thresholds: {e}. Using validator defaults.")
                        context.thresholds = {}  # Empty dict - validators will use defaults

                # FASE 1: Quality Validation (validates output quality, not just errors)
                if spec.quality_validator:
                    logger.info(f"  🔍 Running quality validation for {agent_name}...")

                    try:
                        is_valid, validation_error = spec.quality_validator(output, context)

                        if not is_valid:
                            logger.warning(f"  ⚠️ Quality validation failed: {validation_error}")

                            # Try quality retry if available and retries left
                            if spec.quality_retry_fn and attempt < retries:
                                logger.info(f"  🔧 Attempting quality retry (regenerate with constraints)...")

                                from yt_autopilot.core.logger import log_fallback
                                log_fallback(
                                    component=agent_name.upper(),
                                    fallback_type="QUALITY_RETRY",
                                    reason=validation_error,
                                    impact="MEDIUM"
                                )

                                try:
                                    # Regenerate with quality constraints
                                    output = spec.quality_retry_fn(output, context, validation_error)

                                    # Re-validate after retry
                                    is_valid_after_retry, retry_error = spec.quality_validator(output, context)

                                    if not is_valid_after_retry:
                                        logger.warning(f"  ⚠️ Quality still invalid after retry: {retry_error}")
                                        # Continue to next retry attempt (error retry)
                                        raise Exception(f"Quality validation failed after retry: {retry_error}")

                                    logger.info(f"  ✅ Quality retry succeeded!")

                                except Exception as retry_err:
                                    logger.error(f"  ❌ Quality retry failed: {str(retry_err)[:100]}")
                                    # Continue to next retry attempt
                                    raise

                            else:
                                # No quality retry available or max retries reached
                                if not spec.quality_retry_fn:
                                    logger.warning(f"  ⚠️ No quality_retry_fn configured, continuing with invalid output")
                                else:
                                    logger.warning(f"  ⚠️ Max retries reached, continuing with invalid output")

                        else:
                            logger.info(f"  ✅ Quality validation passed")

                    except Exception as val_err:
                        logger.error(f"  ❌ Quality validator itself failed: {str(val_err)[:100]}")
                        # Don't block pipeline if validator fails - log and continue

                # Record successful call
                call_record = AgentCallRecord(
                    agent_name=agent_name,
                    started_at=start_time,
                    completed_at=time.time(),
                    status="success",
                    execution_time_ms=execution_time_ms,
                    retry_count=attempt
                )
                context.agent_call_history.append(call_record)

                logger.info(f"  ✅ {agent_name} completed in {execution_time_ms:.0f}ms")

                return AgentResult(
                    agent_name=agent_name,
                    status="success",
                    output=output,
                    execution_time_ms=execution_time_ms,
                    retry_count=attempt,
                    metadata={"spec": spec}
                )

            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
                logger.warning(f"  ⚠️ {agent_name} failed (attempt {attempt + 1}): {str(e)[:100]}")

                if attempt < retries:
                    logger.info(f"  🔄 Retrying {agent_name}...")
                    continue
                else:
                    # Max retries reached - use fallback or fail
                    logger.error(f"  ❌ {agent_name} failed after {retries + 1} attempts")

                    if spec.fallback_strategy:
                        logger.info(f"  🔧 Using fallback strategy for {agent_name}")

                        try:
                            fallback_output = spec.fallback_strategy(context)

                            call_record = AgentCallRecord(
                                agent_name=agent_name,
                                started_at=start_time if 'start_time' in locals() else time.time(),
                                completed_at=time.time(),
                                status="fallback",
                                execution_time_ms=execution_time_ms,
                                retry_count=retries,
                                error_message=str(e)
                            )
                            context.agent_call_history.append(call_record)

                            error = AgentError(
                                agent_name=agent_name,
                                error_type="max_retries",
                                message=f"Max retries ({retries}) exceeded, fallback used",
                                original_error=e,
                                retry_count=retries,
                                is_recoverable=True,
                                fallback_used=True
                            )

                            context.errors.append(error)

                            logger.info(f"  ✅ Fallback succeeded for {agent_name}")

                            return AgentResult(
                                agent_name=agent_name,
                                status="fallback",
                                output=fallback_output,
                                execution_time_ms=execution_time_ms,
                                retry_count=retries,
                                error=error,
                                metadata={"fallback_used": True}
                            )

                        except Exception as fallback_error:
                            logger.error(f"  ❌ Fallback also failed: {fallback_error}")
                            # Fall through to failure case
                            e = fallback_error

                    # No fallback or fallback failed - complete failure
                    call_record = AgentCallRecord(
                        agent_name=agent_name,
                        started_at=start_time if 'start_time' in locals() else time.time(),
                        completed_at=time.time(),
                        status="failed",
                        execution_time_ms=execution_time_ms,
                        retry_count=retries,
                        error_message=str(e)
                    )
                    context.agent_call_history.append(call_record)

                    error = AgentError(
                        agent_name=agent_name,
                        error_type="agent_failure",
                        message=str(e),
                        original_error=e,
                        retry_count=retries,
                        is_recoverable=False,
                        fallback_used=False
                    )

                    context.errors.append(error)

                    return AgentResult(
                        agent_name=agent_name,
                        status="failed",
                        output=None,
                        execution_time_ms=execution_time_ms,
                        retry_count=retries,
                        error=error
                    )

    def _call_agent_with_adaptation(
        self,
        spec: AgentSpec,
        context: AgentContext
    ) -> Any:
        """
        Calls agent function with parameter adaptation.

        Converts unified AgentContext to agent-specific function signatures.
        This adapter layer ensures backward compatibility - NO changes required
        to existing agents.

        Args:
            spec: AgentSpec with function to call
            context: Current AgentContext

        Returns:
            Agent output (type varies by agent)

        Raises:
            Exception: If agent function fails
        """
        # Import dependencies as needed
        from yt_autopilot.core.config import get_vertical_config

        if spec.name == "editorial_strategist":
            return spec.function(
                trend=context.selected_trend,
                workspace=context.workspace,
                llm_generate_fn=context.llm_generate_fn,
                performance_history=context.performance_history or []
            )

        elif spec.name == "duration_strategist":
            return spec.function(
                topic=context.video_plan.working_title,
                vertical_id=context.workspace.get('vertical_id', 'general'),
                workspace_config=context.workspace,
                vertical_config=get_vertical_config(context.workspace.get('vertical_id', 'general')),
                trend_data={
                    'source': context.selected_trend.source if context.selected_trend else 'unknown',
                    'engagement_score': context.selected_trend.momentum_score if context.selected_trend else 0.5,
                    'virality_potential': context.selected_trend.virality_score if context.selected_trend else 0.5
                }
            )

        elif spec.name == "format_reconciler":
            return spec.function(
                editorial_decision=context.editorial_decision,
                duration_strategy=context.duration_strategy,
                llm_generate_fn=context.llm_generate_fn,
                workspace_config=context.workspace
            )

        elif spec.name == "narrative_architect":
            return spec.function(
                topic=context.video_plan.working_title,
                target_duration_seconds=context.duration_strategy.get('target_duration_seconds', 60) if context.duration_strategy else 60,
                workspace_config=context.workspace,
                editorial_decision=context.editorial_decision,
                llm_generate_fn=context.llm_generate_fn
            )

        elif spec.name == "cta_strategist":
            return spec.function(
                editorial_decision=context.editorial_decision,
                duration_strategy=context.duration_strategy,
                narrative_arc=context.narrative_arc,
                workspace_config=context.workspace,
                llm_generate_fn=context.llm_generate_fn
            )

        elif spec.name == "content_depth_strategist":
            return spec.function(
                topic=context.video_plan.working_title,
                # Phase C - P0: Access Timeline.reconciled_duration instead of dict['final_duration']
                target_duration=context.reconciled_format.reconciled_duration if context.reconciled_format else 60,
                narrative_arc=context.narrative_arc or {},
                editorial_decision=context.editorial_decision,
                workspace=context.workspace,
                llm_generate_fn=context.llm_generate_fn
            )

        elif spec.name == "script_writer":
            return spec.function(
                video_plan=context.video_plan,
                memory=context.memory or {},
                llm_suggestion=None,  # Legacy parameter
                series_format=context.series_format,
                editorial_decision=context.editorial_decision,
                narrative_arc=context.narrative_arc,
                content_depth_strategy=context.content_depth_strategy
            )

        elif spec.name == "visual_planner":
            return spec.function(
                video_plan=context.video_plan,
                script=context.script,
                memory=context.memory or {},
                workspace_config=context.workspace,
                duration_strategy=context.duration_strategy
            )

        elif spec.name == "seo_manager":
            return spec.function(
                video_plan=context.video_plan,
                script=context.script
            )

        elif spec.name == "quality_reviewer":
            return spec.function(
                video_plan=context.video_plan,
                script=context.script,
                visuals=context.visual_plan,
                memory=context.memory or {}
            )

        elif spec.name == "monetization_qa":
            # Import here to avoid circular dependencies
            from yt_autopilot.agents.monetization_qa import validate_monetization_readiness

            return spec.function(
                duration_strategy=context.duration_strategy,
                narrative_arc=context.narrative_arc,
                content_depth_strategy=context.content_depth_strategy,
                script=context.script,
                reconciled_format=context.reconciled_format,
                editorial_decision=context.editorial_decision,
                workspace=context.workspace,
                llm_generate_fn=context.llm_generate_fn
            )

        else:
            raise ValueError(f"No adapter implemented for agent: {spec.name}")

    def execute_pipeline(
        self,
        context: AgentContext,
        mode: str = "linear"
    ) -> Dict:
        """
        Execute full editorial pipeline.

        Modes:
        - "linear": Fixed agent sequence (backward compatible with build_video_package.py)
        - "ai_driven": LLM-powered orchestration (Phase A4 Sprint 2 - not yet implemented)

        Args:
            context: Initial AgentContext with workspace, video_plan, llm_fn
            mode: Execution mode ("linear" or "ai_driven")

        Returns:
            Dict with pipeline results:
            {
                "status": "success" | "failed",
                "context": AgentContext (final state),
                "summary": {
                    "agents_called": int,
                    "total_time_ms": float,
                    "errors": int,
                    "fallbacks": int
                }
            }

        Example:
            context = AgentContext(
                workspace=workspace,
                video_plan=video_plan,
                llm_generate_fn=llm_generate_fn,
                workspace_id=workspace_id,
                execution_id=str(uuid.uuid4())
            )

            result = coordinator.execute_pipeline(context, mode="linear")
            if result["status"] == "success":
                final_script = result["context"].script
                final_visual_plan = result["context"].visual_plan
        """
        logger.info("")
        logger.info("=" * 70)
        logger.info(f"AGENT COORDINATOR: Starting Pipeline (mode={mode})")
        logger.info(f"  Execution ID: {context.execution_id}")
        logger.info(f"  Workspace: {context.workspace_id}")
        logger.info("=" * 70)
        logger.info("")

        if mode == "ai_driven":
            raise NotImplementedError(
                "AI-driven orchestration coming in Phase A4 Sprint 2. "
                "Use mode='linear' for now."
            )

        # Execute linear pipeline (backward compatible)
        return self._execute_linear_pipeline(context)

    def _execute_linear_pipeline(self, context: AgentContext) -> Dict:
        """
        Execute pipeline in fixed linear sequence.

        This mode is backward compatible with existing build_video_package.py logic.
        Agents are called in a hardcoded sequence, with dependency checks enforced.

        Args:
            context: AgentContext with initial state

        Returns:
            Dict with pipeline results
        """
        # Define fixed agent sequence
        # NOTE: This is the same sequence as build_video_package.py for backward compatibility
        sequence = [
            "editorial_strategist",
            "duration_strategist",
            "format_reconciler",
            "narrative_architect",
            "cta_strategist",
            "content_depth_strategist",
            "script_writer",
            "visual_planner",
            "seo_manager",
            "quality_reviewer",
            "monetization_qa"
        ]

        logger.info(f"Linear pipeline sequence: {len(sequence)} agents")
        logger.info(f"Agents: {', '.join(sequence)}")
        logger.info("")

        # Execute agents in sequence
        for i, agent_name in enumerate(sequence, 1):
            logger.info(f"[{i}/{len(sequence)}] Calling {agent_name}...")

            result = self.call_agent(agent_name, context)

            if result.status == "failed":
                spec = self.registry.get(agent_name)

                if spec and spec.is_critical:
                    logger.error("")
                    logger.error("=" * 70)
                    logger.error(f"CRITICAL AGENT FAILED: {agent_name}")
                    logger.error(f"  Error: {result.error.message if result.error else 'Unknown'}")
                    logger.error("  Stopping pipeline (critical agent failure)")
                    logger.error("=" * 70)

                    return {
                        "status": "failed",
                        "context": context,
                        "failed_agent": agent_name,
                        "error": result.error,
                        "summary": self._create_summary(context)
                    }
                else:
                    logger.warning(f"Non-critical agent {agent_name} failed - continuing pipeline")

            # Store output in context
            if result.output:
                context.set_agent_output(agent_name, result.output)
                logger.info(f"  ✓ {agent_name} output stored in context")

            logger.info("")

        # All agents completed successfully
        logger.info("=" * 70)
        logger.info("PIPELINE COMPLETED SUCCESSFULLY")
        logger.info("=" * 70)

        summary = self._create_summary(context)

        logger.info("")
        logger.info("Pipeline Summary:")
        logger.info(f"  Agents called: {summary['agents_called']}")
        logger.info(f"  Total time: {summary['total_time_ms']:.0f}ms ({summary['total_time_ms']/1000:.1f}s)")
        logger.info(f"  Average per agent: {summary['avg_time_per_agent_ms']:.0f}ms")
        logger.info(f"  Errors: {summary['errors']}")
        logger.info(f"  Fallbacks used: {summary['fallbacks']}")
        logger.info("=" * 70)

        return {
            "status": "success",
            "context": context,
            "summary": summary
        }

    def _create_summary(self, context: AgentContext) -> Dict:
        """
        Create execution summary for analytics.

        Args:
            context: AgentContext with execution history

        Returns:
            Dict with summary statistics
        """
        total_time_ms = context.get_total_execution_time_ms()
        agents_called = context.get_agent_count()

        return {
            "agents_called": agents_called,
            "total_time_ms": total_time_ms,
            "avg_time_per_agent_ms": total_time_ms / agents_called if agents_called > 0 else 0,
            "errors": context.get_error_count(),
            "fallbacks": context.get_fallback_count(),
            "execution_id": context.execution_id,
            "workspace_id": context.workspace_id
        }

    def create_content_package(self, context: AgentContext, status: str = "APPROVED", rejection_reason: Optional[str] = None) -> Any:
        """
        Create ContentPackage from AgentContext.

        This converts the final pipeline state into a ContentPackage
        compatible with build_video_package.py return type.

        Args:
            context: Final AgentContext after pipeline execution
            status: "APPROVED", "REJECTED", or "NEEDS_REVISION"
            rejection_reason: Reason for rejection (if status != APPROVED)

        Returns:
            ContentPackage with all agent outputs

        Note:
            Import ContentPackage here to avoid circular dependency
        """
        from yt_autopilot.core.schemas import ContentPackage

        # Extract reasoning strings from agent outputs
        duration_reasoning = context.duration_strategy.get('reasoning', '') if context.duration_strategy else ''
        # Phase C - P0: Access Timeline.arbitration_reasoning instead of dict['reasoning']
        format_reasoning = context.reconciled_format.arbitration_reasoning if context.reconciled_format else ''
        narrative_reasoning = context.narrative_arc.get('reasoning', '') if context.narrative_arc else ''
        cta_reasoning = context.cta_strategy.get('reasoning', '') if context.cta_strategy else ''

        return ContentPackage(
            status=status,
            video_plan=context.video_plan,
            script=context.script,
            visuals=context.visual_plan,
            publishing=context.publishing,
            rejection_reason=rejection_reason,
            llm_raw_script=None,  # AgentCoordinator doesn't track raw script (could be added to context)
            final_script_text=context.script.full_voiceover_text if context.script else '',
            editorial_decision=context.editorial_decision,
            duration_strategy_reasoning=duration_reasoning,
            format_reconciliation_reasoning=format_reasoning,
            narrative_design_reasoning=narrative_reasoning,
            cta_strategy_reasoning=cta_reasoning
        )


# ============================================================================
# FASE 1: QUALITY VALIDATORS & RETRY FUNCTIONS
# ============================================================================
#
# Quality validators check output quality (not just errors).
# Quality retry functions regenerate output with constraints.
#
# Pattern:
#   validator(output, context) -> (is_valid: bool, error_msg: str)
#   retry_fn(output, context, error_msg) -> new_output
# ============================================================================

def validate_narrative_bullet_count(narrative_arc: Dict, context: AgentContext) -> tuple[bool, Optional[str]]:
    """
    Quality validator for Narrative Architect.

    Validates that narrative arc bullet count matches Content Depth Strategy recommendation.

    Args:
        narrative_arc: Output from Narrative Architect (dict with 'narrative_structure' key)
        context: AgentContext with content_depth_strategy populated

    Returns:
        (is_valid, error_msg): (True, None) if valid, (False, error_msg) if invalid

    Example:
        is_valid, error = validate_narrative_bullet_count(narrative_arc, context)
        if not is_valid:
            # Trigger quality retry
    """
    # Skip validation if no content depth strategy
    if not context.content_depth_strategy:
        return True, None

    recommended_bullets = context.content_depth_strategy.get('recommended_bullets')
    if not recommended_bullets:
        return True, None

    # Extract narrative structure
    narrative_structure = narrative_arc.get('narrative_structure', [])
    if not narrative_structure:
        return False, "Narrative structure is empty"

    # Extract content acts (exclude hook and CTA)
    # CRITICAL FIX: Check ALL acts, not just [1:-1], because narrative structure can vary
    content_acts = []
    for act in narrative_structure:  # Check ALL acts (not just middle ones)
        act_name = act.get('act_name', '').lower()
        # Exclude hook, CTA, outro, payoff acts
        if act_name not in ['hook', 'payoff_cta', 'cta', 'outro', 'payoff', 'call_to_action']:
            content_acts.append(act)

    actual_bullets = len(content_acts)

    # FASE 2.4: Load thresholds from context (with defaults if not available)
    thresholds = context.thresholds or {}
    bullet_count_config = thresholds.get('narrative_bullet_count', {})
    max_deviation = bullet_count_config.get('max_deviation', 1)  # Default: ±1 bullet allowed
    strict_mode = bullet_count_config.get('strict_mode', True)  # Default: trigger retry

    # Calculate deviation
    deviation = abs(actual_bullets - recommended_bullets)

    # Validate count
    if deviation > max_deviation:
        if strict_mode:
            # Strict mode: trigger quality retry
            return False, f"Expected {recommended_bullets} bullets (±{max_deviation} allowed), got {actual_bullets} (deviation: {deviation})"
        else:
            # Lenient mode: log warning but allow (don't block pipeline)
            from yt_autopilot.core.logger import logger
            logger.warning(f"  Bullet count deviation: {deviation} > {max_deviation} (allowed in non-strict mode)")
            return True, None

    # Valid: within allowed deviation
    return True, None


def regenerate_narrative_with_bullet_constraint(
    narrative_arc: Dict,
    context: AgentContext,
    validation_error: str
) -> Dict:
    """
    Quality retry function for Narrative Architect.

    Regenerates narrative arc with explicit bullet count constraint.

    Args:
        narrative_arc: Original (invalid) narrative arc
        context: AgentContext with all pipeline state
        validation_error: Error message from validator (for logging)

    Returns:
        New narrative arc with correct bullet count

    Note:
        This requires narrative_architect.design_narrative_arc() to accept
        bullet_count_constraint parameter (FASE 1.5).
    """
    from yt_autopilot.agents.narrative_architect import design_narrative_arc
    from yt_autopilot.core.logger import logger

    recommended_bullets = context.content_depth_strategy.get('recommended_bullets')

    logger.info(f"  🔧 Regenerating Narrative Arc with bullet_count_constraint={recommended_bullets}")

    # Call Narrative Architect again with explicit bullet count constraint
    new_narrative_arc = design_narrative_arc(
        topic=context.video_plan.working_title,
        target_duration_seconds=context.duration_strategy['target_duration_seconds'],
        workspace_config=context.workspace,
        duration_strategy=context.duration_strategy,
        editorial_decision=context.editorial_decision.__dict__ if hasattr(context.editorial_decision, '__dict__') else context.editorial_decision,
        bullet_count_constraint=recommended_bullets  # NEW parameter (FASE 1.5)
    )

    return new_narrative_arc


# ============================================================================
# FASE 3: Semantic CTA Validation (Quality Validator + Retry)
# ============================================================================

def validate_cta_semantic_match(
    script: 'VideoScript',
    context: AgentContext
) -> tuple[bool, Optional[str]]:
    """
    Quality validator for Script Writer (FASE 3: Semantic CTA matching).

    Validates that script CTA matches CTA Strategist recommendation using semantic similarity.
    Replaces character-based similarity (SequenceMatcher) with semantic embeddings to reduce
    false positives from paraphrasing.

    Args:
        script: VideoScript output from script_writer
        context: AgentContext with cta_strategy and thresholds

    Returns:
        tuple: (is_valid: bool, error_message: Optional[str])

    Example:
        Expected CTA: "Subscribe for crypto alerts"
        Actual CTA: "Don't miss our next video - subscribe!"
        Character similarity: 20% (would fail)
        Semantic similarity: 82% (passes)
    """
    # Check if CTA strategy exists
    if not context.cta_strategy:
        logger.debug("No CTA strategy in context, skipping CTA validation")
        return True, None

    expected_cta = context.cta_strategy.get('main_cta', '')
    if not expected_cta:
        logger.debug("No main_cta in CTA strategy, skipping validation")
        return True, None

    actual_cta = script.outro_cta
    if not actual_cta:
        return False, "Script has empty outro_cta"

    # Load thresholds from context
    thresholds = context.thresholds or {}
    cta_config = thresholds.get('cta_similarity', {})
    use_semantic = cta_config.get('use_semantic', False)
    pass_threshold = cta_config.get('pass_threshold', 0.70)

    # Compute similarity (semantic or character-based)
    if use_semantic:
        try:
            from yt_autopilot.utils.semantic_similarity import semantic_similarity
            similarity = semantic_similarity(expected_cta, actual_cta, use_semantic=True)
            logger.debug(f"Semantic CTA similarity: {similarity:.2f}")
        except ImportError:
            logger.warning("sentence-transformers not installed, falling back to character-based")
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, expected_cta, actual_cta).ratio()
            logger.debug(f"Character CTA similarity (fallback): {similarity:.2f}")
    else:
        # Character-based (legacy)
        from difflib import SequenceMatcher
        similarity = SequenceMatcher(None, expected_cta, actual_cta).ratio()
        logger.debug(f"Character CTA similarity: {similarity:.2f}")

    # Validate against threshold
    if similarity < pass_threshold:
        return False, (
            f"CTA similarity {similarity:.2f} < {pass_threshold} threshold. "
            f"Expected: '{expected_cta[:60]}...', Got: '{actual_cta[:60]}...'"
        )

    logger.debug(f"✓ CTA similarity validation passed ({similarity:.2f} >= {pass_threshold})")
    return True, None


def regenerate_script_with_cta_fix(
    script: 'VideoScript',
    context: AgentContext,
    validation_error: str
) -> 'VideoScript':
    """
    Quality retry function for Script Writer (FASE 3: Force specific CTA).

    Regenerates script with forced CTA from CTA Strategist to ensure exact match.

    Args:
        script: Original VideoScript with mismatched CTA
        context: AgentContext with cta_strategy
        validation_error: Error message from validator

    Returns:
        VideoScript: New script with forced CTA

    Flow:
        1. Extract expected CTA from context.cta_strategy
        2. Call write_script() with forced_cta parameter
        3. LLM generates new script with exact CTA text
    """
    from yt_autopilot.agents.script_writer import write_script

    # Extract expected CTA
    expected_cta = context.cta_strategy.get('main_cta', '') if context.cta_strategy else ''

    if not expected_cta:
        logger.error("Cannot regenerate script: no main_cta in context")
        return script  # Return original if no CTA available

    logger.info(f"Forcing CTA: '{expected_cta[:60]}...'")

    # Regenerate script with forced CTA
    improved_script = write_script(
        plan=context.video_plan,
        memory=context.memory or {},
        llm_suggestion=None,  # Will regenerate fresh
        series_format=context.series_format,
        editorial_decision=context.editorial_decision,
        narrative_arc=context.narrative_arc,
        content_depth_strategy=context.content_depth_strategy,
        forced_cta=expected_cta  # NEW PARAMETER (FASE 3)
    )

    return improved_script


# ============================================================================
# PLACEHOLDER: Future AI-Driven Orchestration (Phase A4 Sprint 2)
# ============================================================================

# class AdaptiveAgentOrchestrator:
#     """
#     LLM-powered orchestrator for dynamic agent selection.
#     NO HARDCODED SEQUENCES - uses AI reasoning.
#
#     Features (planned):
#     - Dynamic agent selection based on context
#     - Parallel execution where possible
#     - Quality-based early stopping
#     - Intelligent error recovery
#     """
#     pass
