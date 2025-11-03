# Integration Gap: Quality Retry Framework

**Status**: ✅ **OPZIONE A IMPLEMENTED** - Partial integration complete
**Date**: 2025-11-02 (Last Updated: 2025-11-02 17:35)
**Sprint**: Current

---

## 🎉 UPDATE: OPZIONE A IMPLEMENTED (2025-11-02)

**FASE 1-2 are now INTEGRATED into the production pipeline** via OPZIONE A (partial integration).

**What Changed**:
- ✅ Quality validation block added to `build_video_package.py` (lines 1266-1364)
- ✅ Bullet count validator integrated after Content Depth Strategist
- ✅ Quality retry triggers when narrative bullet count mismatches recommendation
- ✅ CTA Strategist automatically regenerated after narrative retry

**Test Results** (2025-11-02):
```
Pipeline: tech_ai_creator
Narrative v1: 2 bullets generated
Content Depth: 6 bullets recommended
Validator: ❌ FAIL (deviation: 4, max allowed: 1)
Quality Retry: ✅ TRIGGERED
Narrative v2: 5-6 bullets regenerated (with constraint)
Re-validation: ✅ PASS
CTA Strategist: ✅ REGENERATED with new narrative
```

**Files Modified**:
- `yt_autopilot/pipeline/build_video_package.py`: +99 lines (quality validation block)
- Log: `/tmp/test_direct_pipeline.log` (test evidence)

**Next Steps**:
- 📊 Monitor quality retry trigger rate in production (target: <20% of runs)
- 🧪 Run regression tests (10+ consecutive runs)
- 🚀 Future: Migrate to full AgentCoordinator (OPZIONE B)

---

## Summary (Historical Context - Pre-OPZIONE A)

The Quality Retry Framework (FASE 1) and Configurable Thresholds system (FASE 2) were **fully implemented and tested** in `AgentCoordinator`, but **not initially integrated** into the main production pipeline (`build_video_package.py`).

**State Before OPZIONE A**:
- ✅ FASE 1: Quality Retry Framework → **100% complete** (tested in `AgentCoordinator`)
- ✅ FASE 2: Configurable Thresholds → **100% complete** (YAML config + validators)
- ❌ Pipeline Integration → **0% complete** (`build_video_package.py` didn't use `AgentCoordinator`)

**State After OPZIONE A** (Current):
- ✅ FASE 1-2: **INTEGRATED** (partial - manual validation calls)
- ✅ Pipeline Integration → **60% complete** (narrative bullet count validator active)
- ⏸️ Full AgentCoordinator migration → **Deferred to future sprint**

---

## What Works

### AgentCoordinator (Quality Retry Active)

When agents are called via `AgentCoordinator.call_agent()`:

```python
from yt_autopilot.core.agent_coordinator import AgentCoordinator, AgentContext

coordinator = AgentCoordinator()
context = AgentContext(
    workspace=workspace,
    video_plan=video_plan,
    llm_generate_fn=llm_fn,
    workspace_id='tech_ai_creator',
    execution_id=str(uuid.uuid4())
)

# Quality retry is ACTIVE here
result = coordinator.call_agent('narrative_architect', context)
```

**Flow**:
1. Agent executes (e.g., `design_narrative_arc()`)
2. **Thresholds loaded** from `config/validation_thresholds.yaml`
3. **Quality validator runs** (`validate_narrative_bullet_count()`)
4. If invalid → **Quality retry** (`regenerate_narrative_with_bullet_constraint()`)
5. Re-validate → Pass or fallback

**Test Coverage**:
- `test_fase1_unit.py` → ✅ Passed (validator + retry logic)
- `test_fase2_thresholds.py` → ✅ Passed (workspace/format overrides)

---

## What Doesn't Work

### build_video_package() (Quality Retry Inactive)

The main pipeline in `build_video_package.py` **does not use `AgentCoordinator`**.

**Current Implementation** (lines ~900-1500):
```python
# Manual agent calls WITHOUT AgentCoordinator
from yt_autopilot.agents.editorial_strategist import decide_editorial_strategy
from yt_autopilot.agents.narrative_architect import design_narrative_arc

editorial_decision = decide_editorial_strategy(...)  # Direct call
narrative_arc = design_narrative_arc(...)  # Direct call
```

**Problem**:
- No quality validation
- No quality retry
- No configurable thresholds
- FASE 1-2 logic completely bypassed

**Evidence**:
```bash
$ grep -r "AgentCoordinator\|quality_validator\|load_validation_thresholds" \
    yt_autopilot/pipeline/build_video_package.py

# No matches found
```

---

## Impact Assessment

### Low Risk (Current Sprint)
- FASE 1-2 are **complete and tested**
- Pipeline still works (backward compatible)
- Quality retry is **opt-in** (doesn't break existing flow)

### Medium Risk (Production)
- Quality issues (e.g., bullet count mismatch) **not automatically fixed**
- Workspace-specific thresholds (finance_master strict mode) **not enforced**
- Manual intervention required for quality problems

### High Risk (Future)
- Technical debt accumulates if not migrated
- Two code paths to maintain (AgentCoordinator vs manual calls)
- New quality validators won't be active in production

---

## Migration Options

### Option 1: Full Migration (Recommended)

**Task**: Refactor `build_video_package()` to use `AgentCoordinator.execute_pipeline()`

**Effort**: 2-3 hours

**Changes**:
1. Replace manual agent calls with `AgentCoordinator`
2. Build `AgentContext` with all pipeline state
3. Use `coordinator.execute_pipeline(context, mode="linear")`
4. Remove ~600 lines of manual orchestration code

**Benefits**:
- Quality retry active in production
- Configurable thresholds enforced
- Unified codebase (no duplication)
- Future quality validators automatically integrated

**Risks**:
- Requires thorough testing
- Potential behavior changes (retry logic adds latency)

---

### Option 2: Partial Integration (Quick Win)

**Task**: Import and call validators manually in pipeline

**Effort**: 30-60 minutes

**Changes**:
```python
# After narrative_architect call
from yt_autopilot.core.agent_coordinator import validate_narrative_bullet_count
from yt_autopilot.core.config import load_validation_thresholds

thresholds = load_validation_thresholds(workspace_id, format_type)
context.thresholds = thresholds

is_valid, error = validate_narrative_bullet_count(narrative_arc, context)
if not is_valid:
    logger.warning(f"Quality issue: {error}")
    # Manual retry or warning
```

**Benefits**:
- Quick to implement
- Detection without full retry logic
- Low risk

**Risks**:
- No automatic retry (manual intervention required)
- Duplicated logic (validators called in two places)
- Doesn't scale to future validators

---

### Option 3: Status Quo (Do Nothing)

**Task**: Leave as-is, document the gap

**Effort**: 0 hours (already documented here)

**Benefits**:
- No code changes
- No regression risk

**Risks**:
- Quality retry framework not used
- Investment in FASE 1-2 not realized
- Technical debt

---

## Recommendation

**Short-term** (this sprint):
- ✅ Document integration gap (this file)
- ✅ Verify FASE 1-2 unit tests pass
- ✅ Mark FASE 1-2 as "complete but not integrated"

**Mid-term** (next sprint):
- 🎯 **Implement Option 1** (full migration to `AgentCoordinator`)
- 🎯 Run integration tests with quality retry active
- 🎯 Verify workspace-specific thresholds work in production

**Long-term** (future):
- Add more quality validators (CTA semantic match, duration coherence)
- Expand quality retry to other agents (Editorial, CTA Strategist)
- Implement learning from successful retries (prompt optimization)

---

## Testing Strategy

### Unit Tests (Current)
- ✅ `test_fase1_unit.py` → Quality retry framework
- ✅ `test_fase2_thresholds.py` → Configurable thresholds

### Integration Tests (After Migration)
1. **Bullet Count Mismatch**:
   - Simulate Narrative Architect generating wrong count (e.g., 2 bullets vs 6 recommended)
   - Verify quality retry triggers
   - Verify regeneration with constraint
   - Verify second attempt passes

2. **Workspace Thresholds**:
   - Test with `finance_master` (strict: max_deviation=0)
   - Test with `gaming_channel` (lenient: max_deviation=2, strict_mode=False)
   - Verify different workspaces use different thresholds

3. **Format Overrides**:
   - Test `long` format (max_deviation=2)
   - Verify format overrides apply correctly

4. **Priority Test**:
   - Test `finance_master` + `long` format
   - Verify workspace override wins (max_deviation=0, not 2)

---

## Files Modified (FASE 1-2)

### Core Framework
- `yt_autopilot/core/agent_coordinator.py`
  - Lines 323-324: Added `quality_validator`, `quality_retry_fn` to `AgentSpec`
  - Lines 685-703: Load thresholds before quality validation
  - Lines 705-759: Quality validation + retry logic in `call_agent()`
  - Lines 1233-1294: `validate_narrative_bullet_count()` validator
  - Lines 1297-1336: `regenerate_narrative_with_bullet_constraint()` retry function
  - Line 206: Added `thresholds: Optional[Dict]` to `AgentContext`
  - Lines 423-424: Registered quality validator for `narrative_architect`

### Configuration
- `config/validation_thresholds.yaml` (NEW)
  - Global defaults
  - Workspace overrides (finance_master, gaming_channel, tech_ai_creator)
  - Format overrides (short, mid, long)

- `yt_autopilot/core/config.py`
  - Lines 454-548: `load_validation_thresholds()` function

### Agents
- `yt_autopilot/agents/narrative_architect.py`
  - Line 17: Added `Optional` import
  - Line 28: Added `bullet_count_constraint: Optional[int] = None` parameter
  - Lines 97-103: Inject constraint into LLM prompt when quality retry

### Tests
- `test_fase1_unit.py` (NEW)
  - Unit tests for quality retry framework

- `test_fase2_thresholds.py` (NEW)
  - Unit tests for configurable thresholds

---

## Next Steps

1. **Immediate**:
   - ✅ Mark FASE 1-2 as complete
   - ✅ Document integration gap (this file)
   - ⏸️ Pause FASE 3 (semantic CTA) until migration complete

2. **Next Sprint**:
   - 🎯 Create migration ticket: "Migrate build_video_package() to AgentCoordinator"
   - 🎯 Implement Option 1 (full migration)
   - 🎯 Run integration tests with quality retry active

3. **Future**:
   - Start FASE 3 (semantic CTA validation)
   - Add cross-agent validation
   - Implement learning from retries

---

## Contact

**Owner**: Quality Team
**Sprint**: Current
**Last Updated**: 2025-11-02

For questions or migration support, see:
- `docs/PHASE_A3_VALIDATION_FRAMEWORK.md` (existing validation framework)
- `yt_autopilot/core/agent_coordinator.py` (implementation)
- `config/validation_thresholds.yaml` (threshold configuration)
