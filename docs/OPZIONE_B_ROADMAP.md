# OPZIONE B Roadmap: Full AgentCoordinator Migration

**Status**: Planned (Post-OPZIONE A)
**Estimated Effort**: 2-3 sprints (~10-12 hours implementation + testing)
**Priority**: Medium (defer until OPZIONE A stabilizes)
**Date**: 2025-11-02

---

## Executive Summary

**Goal**: Refactor `build_video_package()` to use `AgentCoordinator.execute_pipeline()` for unified agent orchestration, eliminating ~600 lines of duplicate code and enabling advanced features like parallel validation and cross-agent quality checks.

**Why**:
- ✅ Unified codebase (no duplication between AgentCoordinator and build_video_package)
- ✅ Scalable (new agents/validators auto-integrated)
- ✅ Future-proof for AI-driven orchestration and learning from retries

**Current State** (Post-OPZIONE A):
- Quality validation integrated via manual calls (partial integration)
- Pipeline still uses manual agent orchestration
- Code duplication between AgentCoordinator and build_video_package

**Target State** (Post-OPZIONE B):
- All agents called via `AgentCoordinator.execute_pipeline()`
- Quality validation automatic for all registered validators
- ~600 lines of orchestration code deleted

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Implementation Plan](#implementation-plan)
3. [Migration Strategy](#migration-strategy)
4. [Testing Strategy](#testing-strategy)
5. [Rollback Plan](#rollback-plan)
6. [Success Criteria](#success-criteria)
7. [Timeline](#timeline)

---

## Architecture Overview

### Current Architecture (OPZIONE A)

```
build_video_package.py:
├── Manual agent calls (~1200 lines)
│   ├── decide_editorial_strategy()
│   ├── analyze_duration_strategy()
│   ├── design_narrative_arc()
│   ├── design_cta_strategy()
│   ├── analyze_content_depth()
│   ├── write_script()
│   ├── generate_visual_plan()
│   └── ... (5 more agents)
│
├── Quality Validation Block (OPZIONE A)
│   ├── Load thresholds manually
│   ├── Call validate_narrative_bullet_count()
│   ├── Trigger retry if needed
│   └── Regenerate CTA Strategist
│
└── Error handling & fallbacks (manual)
```

**Problems**:
- Duplicate orchestration logic (AgentCoordinator has same logic)
- Manual error handling for each agent
- Quality validation only for narrative_architect (hard to scale)
- ~600 lines of boilerplate code

### Target Architecture (OPZIONE B)

```
build_video_package.py:
├── Setup phase (~200 lines)
│   ├── Load workspace
│   ├── Fetch trends
│   ├── Run trend curation (Phase A/B)
│   └── Select trend
│
├── Build AgentContext (~50 lines)
│   └── Populate with workspace, video_plan, LLM fn, etc.
│
├── Execute Pipeline (~5 lines)
│   └── coordinator.execute_pipeline(context, mode="linear")
│
└── Create ContentPackage (~50 lines)
    └── coordinator.create_content_package(result["context"])
```

**AgentCoordinator handles**:
- Agent execution order (dependency resolution)
- Error handling & retries (transient + quality)
- Timeout enforcement
- Performance tracking
- Quality validation (automatic for all agents)
- Fallback logging

**Benefits**:
- ~600 lines deleted
- Unified orchestration
- Scalable (new agents auto-integrated)
- Consistent error handling

---

## Implementation Plan

### Phase 1: Preparation (Sprint 1, Week 1 - 2 hours)

**Goal**: Prepare codebase for migration without breaking existing flow

**Tasks**:

1. **Extract agent call logic into separate functions**
   ```python
   # build_video_package.py
   def _call_editorial_strategist(workspace, video_plan, ...):
       """Wrapper for editorial strategist call."""
       return decide_editorial_strategy(...)

   # Repeat for all 11 agents
   ```

2. **Add comprehensive tests for legacy path**
   ```python
   # test_legacy_pipeline.py
   def test_build_video_package_legacy():
       """Baseline test for legacy pipeline."""
       package = build_video_package(workspace_id='tech_ai_creator')
       assert package.status == 'APPROVED'
       # Save output as baseline for comparison
   ```

3. **Document expected behavior**
   - Input/output contracts for each agent
   - Expected execution order
   - Error handling behavior

**Deliverables**:
- `test_legacy_pipeline.py` (baseline tests)
- `docs/AGENT_CONTRACTS.md` (input/output specs)

---

### Phase 2: AgentRegistry Population (Sprint 1, Week 1-2 - 3 hours)

**Goal**: Ensure all 11 agents are registered in AgentCoordinator with correct dependencies

**Tasks**:

1. **Verify AgentRegistry completeness**
   ```python
   # yt_autopilot/core/agent_coordinator.py
   # Check if all agents from build_video_package are registered:

   registered_agents = [
       'trend_hunter',           # ✅ Already registered
       'editorial_strategist',   # ✅ Already registered
       'duration_strategist',    # ✅ Already registered
       'format_reconciler',      # ✅ Already registered
       'narrative_architect',    # ✅ Already registered (with quality validator)
       'cta_strategist',         # ❓ Check if registered
       'content_depth_strategist', # ❓ Check if registered
       'script_writer',          # ❓ Check if registered
       'visual_planner',         # ❓ Check if registered
       'quality_reviewer',       # ❓ Check if registered
       'monetization_qa'         # ❓ Check if registered
   ]
   ```

2. **Register missing agents**
   ```python
   # Example: Register CTA Strategist
   self.register(AgentSpec(
       name="cta_strategist",
       function=design_cta_strategy,
       is_critical=True,
       max_retries=2,
       timeout_ms=60000,
       dependencies=["editorial_strategist", "duration_strategist", "narrative_architect"],
       description="Designs strategic CTA placement",
       quality_validator=None,  # Future: FASE 3
       quality_retry_fn=None
   ))
   ```

3. **Update dependency graph**
   - Verify execution order matches build_video_package
   - Example dependency chain:
     ```
     trend_hunter
     ├─> editorial_strategist
     │   ├─> duration_strategist
     │   │   ├─> format_reconciler
     │   │   │   ├─> narrative_architect
     │   │   │   │   ├─> cta_strategist
     │   │   │   │   └─> content_depth_strategist
     │   │   │   │       └─> script_writer
     │   │   │   │           └─> visual_planner
     │   │   │   │               ├─> quality_reviewer
     │   │   │   │               └─> monetization_qa
     ```

4. **Test agent execution via coordinator**
   ```python
   # test_agent_coordinator_full.py
   def test_execute_pipeline_dry_run():
       """Test that all 11 agents execute in correct order."""
       coordinator = AgentCoordinator()
       context = build_test_context()
       result = coordinator.execute_pipeline(context, mode="linear")
       assert result["status"] == "success"
       assert len(result["performance_history"]) == 11
   ```

**Deliverables**:
- All 11 agents registered in AgentCoordinator
- Dependency graph validated
- `test_agent_coordinator_full.py` (integration test)

---

### Phase 3: Pipeline Refactor (Sprint 2, Week 1 - 4 hours)

**Goal**: Replace manual agent calls with `execute_pipeline()`

**Tasks**:

1. **Create parallel implementation path**
   ```python
   # build_video_package.py
   def build_video_package(
       workspace_id: Optional[str] = None,
       use_real_trends: bool = False,
       use_llm_curation: bool = False,
       use_coordinator: bool = False  # Feature flag (default: False)
   ):
       if use_coordinator:
           return _build_via_coordinator(workspace_id, use_real_trends, use_llm_curation)
       else:
           return _build_via_legacy(workspace_id, use_real_trends, use_llm_curation)
   ```

2. **Implement coordinator path**
   ```python
   def _build_via_coordinator(workspace_id, use_real_trends, use_llm_curation):
       # Phase 1: Setup (keep same as legacy)
       workspace = load_workspace_config(workspace_id)
       trends = fetch_trends(...)
       selected_trend = curate_trend(...)
       video_plan = generate_video_plan(...)

       # Phase 2: Build AgentContext
       context = AgentContext(
           workspace=workspace,
           video_plan=video_plan,
           llm_generate_fn=llm_generate_fn,
           workspace_id=workspace_id,
           execution_id=str(uuid.uuid4()),
           selected_trend=selected_trend,
           top_candidates=top_candidates,
           performance_history=[],
           memory=memory,
           series_format=series_format
       )

       # Phase 3: Execute pipeline via coordinator
       coordinator = AgentCoordinator()
       result = coordinator.execute_pipeline(context, mode="linear")

       # Phase 4: Handle result
       if result["status"] == "success":
           return coordinator.create_content_package(
               result["context"],
               status="APPROVED"
           )
       else:
           return coordinator.create_content_package(
               result["context"],
               status="REJECTED",
               rejection_reason=result["error"].message
           )
   ```

3. **Migrate agent state to AgentContext**
   - Current: agents return values stored in local variables
   - Target: agents return values stored in `context.*`
   - Example:
     ```python
     # Legacy
     editorial_decision = decide_editorial_strategy(...)

     # Coordinator
     context.editorial_decision = decide_editorial_strategy(...)
     ```

4. **Delete legacy orchestration code**
   - Lines 862-1500 in build_video_package.py (~600 lines)
   - Keep only:
     - Setup phase (lines 517-617)
     - Coordinator path (_build_via_coordinator)
     - ContentPackage creation (lines 1800+)

**Deliverables**:
- `use_coordinator` feature flag implemented
- Coordinator path functional
- Legacy path preserved (for rollback)

---

### Phase 4: Testing & Validation (Sprint 2, Week 2 - 3 hours)

**Goal**: Verify coordinator path produces identical output to legacy

**Tasks**:

1. **A/B comparison tests**
   ```python
   # test_coordinator_vs_legacy.py
   def test_output_equivalence():
       """Verify coordinator produces same output as legacy."""
       # Run legacy
       legacy_package = build_video_package(
           workspace_id='tech_ai_creator',
           use_coordinator=False
       )

       # Run coordinator
       coordinator_package = build_video_package(
           workspace_id='tech_ai_creator',
           use_coordinator=True
       )

       # Compare
       assert legacy_package.script.full_voiceover_text == coordinator_package.script.full_voiceover_text
       assert legacy_package.publishing.final_title == coordinator_package.publishing.final_title
       # ... (more assertions)
   ```

2. **Performance benchmarking**
   ```python
   # Compare execution time
   legacy_time = time_pipeline(use_coordinator=False)  # Baseline
   coordinator_time = time_pipeline(use_coordinator=True)

   # Target: <10% regression
   assert coordinator_time < legacy_time * 1.10
   ```

3. **Error handling tests**
   ```python
   # Test that coordinator handles errors gracefully
   def test_coordinator_agent_failure():
       """Verify coordinator handles agent failures."""
       # Mock agent to fail
       with mock.patch('narrative_architect.design_narrative_arc', side_effect=Exception("LLM error")):
           result = coordinator.execute_pipeline(context)
           assert result["status"] == "failure"
           assert "narrative_architect" in result["error"].failed_agent
   ```

4. **Regression testing**
   ```bash
   # Run 20+ pipeline executions with coordinator
   for i in {1..20}; do
       python3 run.py generate --use-coordinator
   done

   # Verify:
   # - Success rate >95%
   # - Quality retry triggers correctly
   # - No new errors introduced
   ```

**Deliverables**:
- `test_coordinator_vs_legacy.py` (equivalence tests)
- Performance benchmark report
- 20+ successful regression runs

---

### Phase 5: Deployment & Cleanup (Sprint 3, Week 1 - 2 hours)

**Goal**: Roll out coordinator path and deprecate legacy

**Tasks**:

1. **Canary deployment**
   - Enable `use_coordinator=True` for 10% of traffic
   - Monitor error rate, execution time, quality metrics
   - If stable (error rate <2%): increase to 50%
   - If stable (1 week): increase to 100%

2. **Default to coordinator**
   ```python
   # build_video_package.py
   def build_video_package(
       workspace_id: Optional[str] = None,
       use_real_trends: bool = False,
       use_llm_curation: bool = False,
       use_coordinator: bool = True  # DEFAULT TO TRUE
   ):
   ```

3. **Delete legacy code**
   - Remove `_build_via_legacy()` function (~600 lines)
   - Remove `use_coordinator` feature flag
   - Update documentation

4. **Update CLI**
   ```python
   # run.py
   # Remove --use-coordinator flag (no longer needed)
   ```

**Deliverables**:
- Coordinator path is default
- Legacy code deleted
- Documentation updated

---

## Migration Strategy

### Feature Flag Rollout

**Phase 1**: Development (Week 1-2)
- `use_coordinator=False` (default)
- Test coordinator path manually

**Phase 2**: Canary (Week 3)
- `use_coordinator=True` for 10% traffic (randomized by execution_id)
- Monitor: error rate, execution time, quality retry rate
- Alert if error rate >2% vs legacy

**Phase 3**: Ramp (Week 4)
- If canary passes: increase to 50%
- Monitor for 3-5 days
- Alert if regression detected

**Phase 4**: Full Rollout (Week 5)
- `use_coordinator=True` for 100%
- Keep legacy code for 1 week (safety)
- Delete legacy code after stabilization

### Rollback Triggers

Rollback to legacy if:
- Error rate >5% higher than legacy baseline
- Execution time >20% slower than legacy
- Critical agent failures >2% of runs
- Quality validation broken (retry not triggering)

**Rollback Command**:
```python
# Emergency rollback (1 line change)
use_coordinator: bool = False  # Revert to legacy
```

---

## Testing Strategy

### Test Levels

#### 1. Unit Tests (Per-Agent)

```python
# test_agent_coordinator_unit.py
def test_narrative_architect_via_coordinator():
    """Test single agent via coordinator."""
    coordinator = AgentCoordinator()
    context = build_minimal_context()

    result = coordinator.call_agent('narrative_architect', context)

    assert result is not None
    assert 'narrative_structure' in result
    assert len(result['narrative_structure']) > 0
```

#### 2. Integration Tests (Full Pipeline)

```python
# test_coordinator_integration.py
def test_full_pipeline_via_coordinator():
    """Test complete pipeline via coordinator."""
    context = build_full_context()
    coordinator = AgentCoordinator()

    result = coordinator.execute_pipeline(context, mode="linear")

    assert result["status"] == "success"
    assert len(result["performance_history"]) == 11
    assert context.script is not None
    assert context.visual_plan is not None
```

#### 3. Regression Tests (Output Equivalence)

```python
# test_coordinator_vs_legacy.py
def test_output_equivalence_multi_workspace():
    """Verify coordinator produces same output across workspaces."""
    for workspace_id in ['tech_ai_creator', 'finance_master', 'gaming_channel']:
        legacy_pkg = build_video_package(workspace_id, use_coordinator=False)
        coord_pkg = build_video_package(workspace_id, use_coordinator=True)

        # Compare key fields
        assert_packages_equivalent(legacy_pkg, coord_pkg)
```

#### 4. Performance Tests

```python
# test_coordinator_performance.py
def test_execution_time_regression():
    """Verify coordinator doesn't add significant latency."""
    legacy_times = [time_pipeline(use_coordinator=False) for _ in range(10)]
    coord_times = [time_pipeline(use_coordinator=True) for _ in range(10)]

    legacy_avg = sum(legacy_times) / len(legacy_times)
    coord_avg = sum(coord_times) / len(coord_times)

    # Allow <10% regression
    assert coord_avg < legacy_avg * 1.10
```

---

## Rollback Plan

### Scenario 1: Canary Fails (Week 3)

**Trigger**: Error rate >5% vs legacy

**Action**:
1. Immediately set `use_coordinator=False` (default to legacy)
2. Review coordinator execution logs
3. Identify root cause (agent registration? dependency graph? error handling?)
4. Fix issue in dev environment
5. Re-test before re-enabling canary

**Rollback Time**: <5 minutes (1 line change + deploy)

---

### Scenario 2: Ramp Detects Regression (Week 4)

**Trigger**: Execution time >20% slower or quality issues

**Action**:
1. Reduce traffic to 10% (partial rollback)
2. Profile coordinator execution (identify bottleneck)
3. Optimize slow agent calls or add caching
4. Re-test performance
5. Re-ramp gradually

**Rollback Time**: <5 minutes (change traffic percentage)

---

### Scenario 3: Full Rollout Discovers Critical Bug (Week 5)

**Trigger**: Critical agent failures, data corruption, or pipeline blocking

**Action**:
1. Emergency rollback: `use_coordinator=False`
2. Preserve coordinator code (don't delete yet)
3. Root cause analysis (detailed logs, reproduce locally)
4. Fix + test thoroughly
5. Re-deploy with extended canary (2 weeks instead of 1)

**Rollback Time**: <10 minutes (deploy legacy default)

---

## Success Criteria

### Must-Have (Blocking)

- ✅ All 11 agents execute via coordinator in correct order
- ✅ Output equivalence: coordinator produces same ContentPackage as legacy (verified via A/B tests)
- ✅ Error rate <2% higher than legacy baseline
- ✅ Quality validation works (retry triggers correctly)
- ✅ Performance regression <10% (execution time)
- ✅ Rollback plan tested and documented

### Nice-to-Have (Non-Blocking)

- 🎯 Execution time improvement >5% (better orchestration)
- 🎯 Quality retry rate improvement (better validator accuracy)
- 🎯 Cross-agent validation (e.g., CTA ↔ Script consistency check)
- 🎯 Learning from retry patterns (log which agents retry most)

---

## Timeline

### Sprint 1 (Week 1-2): Preparation

| Task | Duration | Owner |
|------|----------|-------|
| Extract agent wrappers | 2h | Dev |
| Add legacy baseline tests | 1h | QA |
| Verify AgentRegistry | 1h | Dev |
| Register missing agents | 2h | Dev |
| Test agent execution order | 1h | QA |

**Total**: ~7 hours

---

### Sprint 2 (Week 3-4): Implementation

| Task | Duration | Owner |
|------|----------|-------|
| Implement feature flag | 1h | Dev |
| Build _build_via_coordinator() | 2h | Dev |
| Migrate agent state to context | 1h | Dev |
| A/B comparison tests | 2h | QA |
| Performance benchmarking | 1h | QA |
| Regression testing (20 runs) | 2h | QA |

**Total**: ~9 hours

---

### Sprint 3 (Week 5-6): Deployment

| Task | Duration | Owner |
|------|----------|-------|
| Canary deployment (10%) | 1 day | DevOps |
| Monitor canary metrics | 2 days | DevOps |
| Ramp to 50% | 1 day | DevOps |
| Ramp to 100% | 1 day | DevOps |
| Delete legacy code | 1h | Dev |
| Update documentation | 1h | Dev |

**Total**: ~5 days + 2 hours

---

## Post-Migration Opportunities

Once OPZIONE B is complete, these advanced features become possible:

### 1. Parallel Agent Execution

```python
# Execute independent agents in parallel
coordinator.execute_pipeline(context, mode="parallel")

# Example: Quality Reviewer + Monetization QA run concurrently
# Savings: ~30s per pipeline run
```

### 2. Cross-Agent Quality Validation

```python
# Validate consistency across multiple agents
def validate_cta_script_consistency(context):
    """Ensure CTA Strategist and Script Writer align."""
    expected_cta = context.cta_strategy['main_cta']
    actual_cta = context.script.outro_cta

    similarity = semantic_similarity(expected_cta, actual_cta)
    return similarity > 0.70

# Register cross-agent validator
coordinator.register_cross_agent_validator(
    name="cta_script_consistency",
    validator=validate_cta_script_consistency,
    agents=["cta_strategist", "script_writer"]
)
```

### 3. Learning from Retry Patterns

```python
# Track which agents retry most frequently
retry_stats = coordinator.get_retry_statistics()
# {
#   'narrative_architect': {'retry_rate': 0.15, 'success_rate': 0.92},
#   'script_writer': {'retry_rate': 0.05, 'success_rate': 0.98}
# }

# Use stats to:
# - Tune prompts for high-retry agents
# - Adjust thresholds dynamically
# - Predict quality issues before they happen
```

### 4. Dynamic Orchestration

```python
# AI-driven agent ordering
coordinator.execute_pipeline(context, mode="adaptive")

# Example: Skip Narrative Architect if editorial decision is "listicle"
# (listicles don't need emotional storytelling)
```

---

## Contact

**Questions or feedback?**
- See: `docs/INTEGRATION_GAP.md` (current state post-OPZIONE A)
- See: `docs/QUALITY_VALIDATION_BEST_PRACTICES.md` (threshold tuning)
- GitHub Issues: Report migration blockers or suggestions

**Last Updated**: 2025-11-02
