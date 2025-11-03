# Quality Validation Best Practices

**Document Version**: 1.0
**Date**: 2025-11-02
**Status**: OPZIONE A Implemented

---

## Overview

This document provides best practices for configuring and tuning quality validation thresholds in the YT Autopilot pipeline, following the implementation of OPZIONE A (partial integration of FASE 1-2 Quality Retry Framework).

---

## Table of Contents

1. [Threshold Configuration](#threshold-configuration)
2. [Workspace-Specific Tuning](#workspace-specific-tuning)
3. [Format-Specific Tuning](#format-specific-tuning)
4. [Monitoring & Analytics](#monitoring--analytics)
5. [Troubleshooting](#troubleshooting)
6. [Performance Optimization](#performance-optimization)

---

## Threshold Configuration

### Global Defaults

**Location**: `config/validation_thresholds.yaml`

```yaml
global:
  narrative_bullet_count:
    max_deviation: 1          # Allow ±1 bullet deviation
    strict_mode: true         # Fail on deviation > max

  cta_similarity:             # Future: FASE 3
    pass_threshold: 0.70      # 70% similarity required
    blocking_threshold: 0.30  # <30% blocks pipeline
    use_semantic: false       # Character-based (for now)
```

**Rationale**:
- `max_deviation: 1` balances quality and LLM variability
- `strict_mode: true` ensures deviations are addressed (via retry)
- Conservative defaults prevent low-quality outputs

### Priority System

Thresholds are applied in this order:

1. **Workspace overrides** (highest priority)
2. **Format overrides** (medium priority)
3. **Global defaults** (lowest priority)

**Example**: `finance_master` workspace + `long` format
- Workspace override: `max_deviation: 0` (strict)
- Format override: `max_deviation: 2` (lenient)
- **Result**: Workspace wins → `max_deviation: 0`

---

## Workspace-Specific Tuning

### When to Use Workspace Overrides

Use workspace overrides when:
- **Brand standards** require exact content structure (e.g., finance, legal)
- **Audience sensitivity** demands consistent quality (e.g., education, children)
- **Monetization tier** justifies stricter quality bar (e.g., high CPM verticals)

### Example Configurations

#### Strict Workspace (Finance, Legal, Education)

```yaml
workspace_overrides:
  finance_master:
    narrative_bullet_count:
      max_deviation: 0        # Exact match required
      strict_mode: true       # Block on mismatch

    cta_similarity:
      pass_threshold: 0.80    # Higher threshold (80%)
      blocking_threshold: 0.40
```

**Use case**: Financial advice channel where structure consistency is critical for trust and compliance.

#### Lenient Workspace (Gaming, Entertainment, Vlog)

```yaml
workspace_overrides:
  gaming_channel:
    narrative_bullet_count:
      max_deviation: 2        # Allow ±2 bullets
      strict_mode: false      # Warning only, don't block

    cta_similarity:
      pass_threshold: 0.60    # Lower threshold (60%)
      blocking_threshold: 0.25
```

**Use case**: Gaming channel where creativity and engagement matter more than strict structure.

#### Balanced Workspace (Tech, AI, Business)

```yaml
workspace_overrides:
  tech_ai_creator:
    # Inherit global defaults
    # (no override needed)
```

**Use case**: Tech/AI channel with moderate quality requirements (use global defaults).

---

## Format-Specific Tuning

### When to Use Format Overrides

Use format overrides when:
- **Duration constraints** affect content density (e.g., shorts vs long)
- **Platform norms** vary by format (e.g., TikTok vs YouTube)
- **Audience expectations** differ (e.g., quick tips vs deep dives)

### Example Configurations

#### Short Format (<3 min)

```yaml
format_overrides:
  short:
    narrative_bullet_count:
      max_deviation: 0        # Shorts need tight structure
      strict_mode: true
```

**Rationale**: Shorts have limited time, so bullet count must match exactly to avoid rushed/incomplete content.

#### Mid Format (3-10 min)

```yaml
format_overrides:
  mid:
    narrative_bullet_count:
      max_deviation: 1        # Use global default
      strict_mode: true
```

**Rationale**: Standard format, balanced quality requirements.

#### Long Format (>10 min)

```yaml
format_overrides:
  long:
    narrative_bullet_count:
      max_deviation: 2        # More flexibility for depth
      strict_mode: true
```

**Rationale**: Long videos can accommodate more variation in content structure without quality loss.

---

## Monitoring & Analytics

### Key Metrics to Track

#### 1. Quality Retry Trigger Rate

**Definition**: % of pipeline runs that trigger quality retry

```bash
# Extract from logs
grep -c "🔧 Attempting quality retry" *.log
```

**Target Ranges**:
- **Healthy**: <20% (LLM mostly follows recommendations)
- **Moderate**: 20-50% (tune Content Depth Strategist prompts)
- **High**: >50% (investigate Content Depth accuracy)

**Action**:
- If >50%: Review Content Depth Strategist prompts
- Check if recommendations are realistic for topic complexity

#### 2. Quality Retry Success Rate

**Definition**: % of retries that pass re-validation

```bash
# Extract from logs
grep -c "✓ Quality retry succeeded" *.log
```

**Target**: >90% success rate

**Action if low**:
- Review `bullet_count_constraint` injection in narrative prompt
- Check if LLM understands constraint instruction

#### 3. Validation Pass Rate (First Attempt)

**Definition**: % of runs that pass validation without retry

**Target**: >80% (indicates good alignment between Content Depth and Narrative Architect)

**Action if low**:
- Improve Content Depth Strategist accuracy
- Adjust thresholds if too strict for workspace

#### 4. Pipeline Completion Rate

**Definition**: % of runs that complete successfully (end-to-end)

**Target**: >95% (quality validation should not block pipeline excessively)

**Action if low**:
- Check if validation is too strict
- Review fallback/error handling in quality retry

---

## Troubleshooting

### Issue 1: High Retry Rate (>50%)

**Symptoms**:
- Most pipeline runs trigger quality retry
- Log: "🔧 Attempting quality retry..." appears frequently

**Root Causes**:
1. Content Depth Strategist recommends unrealistic bullet counts
2. Narrative Architect consistently ignores recommendations
3. Thresholds too strict for workspace

**Solutions**:

**Solution A**: Tune Content Depth prompts
```python
# yt_autopilot/agents/content_depth_strategist.py
# Review LLM prompt for realistic recommendations
# Consider topic complexity, duration, format
```

**Solution B**: Adjust thresholds
```yaml
# Increase max_deviation for this workspace
workspace_overrides:
  my_workspace:
    narrative_bullet_count:
      max_deviation: 2  # Was 1, now 2
```

**Solution C**: Improve Narrative Architect prompts
```python
# yt_autopilot/agents/narrative_architect.py
# Strengthen instruction to follow Content Depth recommendations
```

---

### Issue 2: Low Retry Success Rate (<80%)

**Symptoms**:
- Quality retry triggers but often fails re-validation
- Log: "⚠️ Quality retry failed: ..." appears frequently

**Root Causes**:
1. `bullet_count_constraint` not properly injected into prompt
2. LLM doesn't understand constraint instruction
3. Constraint conflicts with other requirements

**Solutions**:

**Solution A**: Verify constraint injection
```python
# Check yt_autopilot/agents/narrative_architect.py lines 97-103
# Ensure constraint appears in LLM prompt when retry
```

**Solution B**: Strengthen constraint language
```python
# narrative_architect.py prompt
f'''
🔒 CRITICAL CONSTRAINT (Quality Retry):
YOU MUST create EXACTLY {bullet_count_constraint} content acts.
This is a HARD REQUIREMENT from Content Depth Strategist.
DO NOT generate more or fewer acts.
'''
```

**Solution C**: Test with different LLM providers
```bash
# Try GPT-4 vs GPT-3.5 vs Claude
# Some models follow constraints better
```

---

### Issue 3: Validation Not Executing

**Symptoms**:
- Log doesn't contain "Quality Validation: Narrative Bullet Count"
- Validation block skipped

**Root Causes**:
1. `content_depth_strategy` is fallback (no LLM call)
2. `narrative_arc` is None (skipped due to missing dependencies)
3. Validation block condition not met

**Solutions**:

**Solution A**: Check validation condition
```python
# build_video_package.py line 1273
if narrative_arc and content_depth_strategy and not content_depth_strategy.get('_fallback'):
    # Validation runs only if:
    # 1. narrative_arc exists
    # 2. content_depth_strategy exists
    # 3. content_depth_strategy is NOT fallback
```

**Solution B**: Review agent dependencies
```bash
# Ensure Editorial → Duration → Narrative → Content Depth all succeeded
grep -E "(Editorial|Duration|Narrative|Content Depth)" pipeline.log
```

---

### Issue 4: CTA Not Regenerated After Retry

**Symptoms**:
- Quality retry succeeds
- But CTA Strategist uses old narrative (v1)

**Root Causes**:
1. CTA regeneration code not executing
2. Exception in CTA Strategist call

**Solutions**:

**Solution A**: Verify regeneration code
```python
# build_video_package.py lines 1342-1351
# Check if CTA Strategist call happens after retry success
```

**Solution B**: Check for exceptions
```bash
# Look for errors in CTA Strategist after retry
grep -A 5 "Regenerating CTA Strategist" pipeline.log
```

---

## Performance Optimization

### Minimizing Retry Latency

**Problem**: Quality retry adds 10-20s latency per retry

**Solutions**:

1. **Improve First-Attempt Accuracy**
   - Tune Content Depth Strategist prompts
   - Better alignment with Narrative Architect capabilities

2. **Parallel Validation** (Future)
   - Validate multiple agents concurrently
   - Requires full AgentCoordinator migration (OPZIONE B)

3. **Cache LLM Responses** (Future)
   - If same constraint appears multiple times, use cache
   - Requires caching layer in LLM Router

### Reducing False Positives

**Problem**: Validation triggers retry when not needed

**Solutions**:

1. **Adjust Thresholds**
   - Increase `max_deviation` if quality is acceptable
   - Example: `max_deviation: 2` instead of `1`

2. **Disable Strict Mode for Non-Critical Workspaces**
   ```yaml
   workspace_overrides:
     casual_vlog:
       narrative_bullet_count:
         strict_mode: false  # Warning only
   ```

3. **Add More Lenient Format Overrides**
   ```yaml
   format_overrides:
     experimental:
       narrative_bullet_count:
         max_deviation: 3
   ```

---

## Best Practices Summary

### Configuration

✅ **DO**:
- Start with global defaults (`max_deviation: 1`)
- Override for high-stakes workspaces (finance, education)
- Use format overrides sparingly (only when justified)
- Document reasoning for all threshold changes

❌ **DON'T**:
- Set `max_deviation: 0` unless absolutely required (too strict)
- Disable `strict_mode` without monitoring (hides quality issues)
- Override thresholds without testing (may cause high retry rate)
- Use same thresholds for all workspaces (one-size-fits-all doesn't work)

### Monitoring

✅ **DO**:
- Track retry trigger rate weekly
- Monitor retry success rate
- Review failed retries manually (sample 10%)
- Adjust thresholds based on data

❌ **DON'T**:
- Ignore high retry rates (>50%)
- Assume thresholds are correct without validation
- Deploy threshold changes without A/B testing
- Forget to log threshold decisions (for future reference)

### Tuning Process

1. **Start Conservative**: Use global defaults
2. **Monitor**: Track metrics for 50-100 runs
3. **Analyze**: Identify pain points (high retry rate? low success rate?)
4. **Adjust**: Tweak one threshold at a time
5. **Validate**: A/B test new thresholds
6. **Document**: Record why change was made
7. **Iterate**: Repeat process

---

## Future Enhancements

### FASE 3: Semantic CTA Validation

- Replace character-based similarity with semantic embeddings
- Reduce false positives from paraphrasing
- Expected improvement: 15% → <5% false positive rate

### Full AgentCoordinator Migration (OPZIONE B)

- Unified orchestration for all agents
- Parallel validation
- Cross-agent quality checks
- Learning from retry patterns

### Dynamic Threshold Adjustment

- Auto-tune thresholds based on workspace performance
- ML model to predict optimal `max_deviation` per workspace
- Adaptive strict mode (strict for high-CPM, lenient for low-CPM)

---

## Contact

**Questions or feedback?**
- See: `docs/INTEGRATION_GAP.md` (implementation details)
- See: `README.md` lines 1248-1348 (Quality Retry Framework overview)
- GitHub Issues: Report threshold tuning problems

**Last Updated**: 2025-11-02
