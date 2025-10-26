# Step 09: Narrator Persona & Brand Consistency System

**Implementation Date**: 2025-01-26
**Status**: ✅ Phase 1 (Critical) COMPLETED
**Objective**: Maximize retention and sponsorship readiness through workspace-based brand consistency

---

## 🎯 What Was Implemented

### **Phase 1: Critical Features** ✅

1. **Workspace Schema Extension**
   - `narrator_persona`: Character identity, signature phrases, tone of address
   - `voice_config`: TTS voice model and speed configuration
   - `content_formula`: Hook pattern, CTA style, pacing preferences

2. **ScriptWriter Agent Enhancement**
   - `_build_persona_aware_prompt()`: LLM prompt with narrator persona guidelines
   - Format-first, brand-aware adaptation logic
   - Maintains creative freedom while ensuring brand consistency

3. **TTS Service Voice Configuration**
   - Workspace-specific voice model selection (alloy, echo, fable, onyx, nova, shimmer)
   - Configurable playback speed (0.25-4.0x)
   - Automatic fallback to defaults if workspace config missing

4. **Quality Reviewer Validation**
   - `_check_narrator_persona_consistency()`: Validates tone of address (tu/voi)
   - NO rigid signature phrase enforcement
   - Format-appropriate flexibility maintained

---

## 📋 Workspace Schema Reference

### **Full Extended Schema Example** (gym_fitness_pro)

```json
{
  "workspace_id": "gym_fitness_pro",
  "workspace_name": "Gym & Fitness Pro",
  "vertical_id": "fitness",
  "target_language": "it",
  "brand_tone": "Motivazionale, energico, supportivo",
  "visual_style": "Dinamico, colori caldi (arancione, rosso)",
  "banned_topics": [...],
  "recent_titles": [],

  "narrator_persona": {
    "enabled": true,
    "name": "Coach Marco",
    "identity": "Personal trainer certificato ISSA con 10 anni di esperienza",
    "relationship": "coach_motivazionale",
    "tone_of_address": "tu_informale",
    "signature_phrases": [
      "Iniziamo subito!",
      "Ricorda: la costanza batte il talento",
      "Ci vediamo al prossimo allenamento!"
    ],
    "credibility_markers": [
      "Certificazione ISSA",
      "10 anni di esperienza",
      "500+ clienti seguiti"
    ]
  },

  "voice_config": {
    "tts_provider": "openai",
    "voice_model": "nova",
    "speed": 1.1,
    "emotional_tone": "energetic"
  },

  "content_formula": {
    "hook_pattern": "energetic_question",
    "cta_style": "direct_action",
    "target_duration_seconds": 60,
    "pacing": "fast"
  }
}
```

### **Field Descriptions**

#### **narrator_persona**

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `enabled` | boolean | Enable/disable narrator persona | `true` |
| `name` | string | Character name | `"Coach Marco"` |
| `identity` | string | Professional identity | `"Personal trainer certificato"` |
| `relationship` | string | Relationship with audience | `"coach_motivazionale"` |
| `tone_of_address` | string | tu/voi preference | `"tu_informale"` or `"voi_formale"` |
| `signature_phrases` | array | Recurring catchphrases (3 max) | Opening, middle, closing phrases |
| `credibility_markers` | array | Trust-building credentials | Certifications, experience, stats |

#### **voice_config**

| Field | Type | Description | Options |
|-------|------|-------------|---------|
| `tts_provider` | string | TTS provider | `"openai"` (future: elevenlabs, google_tts) |
| `voice_model` | string | Voice identifier | OpenAI: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer` |
| `speed` | float | Playback speed | 0.25-4.0 (1.0 = normal, 1.1 = energetic) |
| `emotional_tone` | string | Future parameter | `"energetic"`, `"calm"`, `"professional"` |

**Voice Model Characteristics** (OpenAI TTS):
- `alloy`: Neutral, versatile
- `echo`: Authoritative, professional
- `fable`: Warm, storytelling
- `onyx`: Deep, masculine
- `nova`: Energetic, friendly (best for fitness)
- `shimmer`: Light, cheerful

#### **content_formula**

| Field | Type | Description | Options |
|-------|------|-------------|---------|
| `hook_pattern` | string | Opening style | `"energetic_question"`, `"statement"`, `"stat_shock"`, `"story_hook"` |
| `cta_style` | string | Call-to-action style | `"direct_action"`, `"soft_ask"`, `"question"` |
| `target_duration_seconds` | int | Target video length | 60 (Shorts max 90) |
| `pacing` | string | Editing speed | `"fast"`, `"medium"`, `"slow"` |

---

## 🔄 How It Works: Memory Flow

```
┌─────────────────────────────────────────────┐
│  WORKSPACE CONFIG (workspaces/*.json)       │
│  - narrator_persona                         │
│  - voice_config                             │
│  - content_formula                          │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  SCRIPTWRITER AGENT                         │
│  _build_persona_aware_prompt()              │
│  → Passes narrator identity to LLM          │
│  → Format-first, brand-aware adaptation     │
│  → Creative freedom maintained              │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  QUALITY REVIEWER                           │
│  _check_narrator_persona_consistency()      │
│  → Validates tone of address (tu/voi)       │
│  → NO rigid signature phrase enforcement    │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  TTS SERVICE                                │
│  synthesize_voiceover(workspace_config)     │
│  → Uses voice_model from workspace          │
│  → Uses speed from workspace                │
│  → Consistent voice across all videos       │
└─────────────────────────────────────────────┘
```

---

## 🧪 Testing Guide

### **Test 1: Verify Workspace Schema**

```bash
# Check that all workspaces have new fields
cat workspaces/gym_fitness_pro.json | jq '.narrator_persona'
cat workspaces/gym_fitness_pro.json | jq '.voice_config'
cat workspaces/gym_fitness_pro.json | jq '.content_formula'
```

**Expected Output**:
- `gym_fitness_pro`: `narrator_persona.enabled = true`
- Other workspaces: `narrator_persona.enabled = false`

---

### **Test 2: Generate Script with Narrator Persona**

```bash
# Switch to gym_fitness_pro workspace
python run.py --switch-workspace gym_fitness_pro

# Generate script (Gate 1)
python run.py --generate-script "2025-01-27T18:00:00"
```

**Expected Behavior**:
1. ScriptWriter logs: `"Narrator persona enabled: Coach Marco"`
2. Script hook may include narrator name (format-dependent)
3. Script uses "tu informale" tone (ti/tu, not vi/voi)
4. Quality Reviewer checks tone of address

**Validation**:
```bash
# Review generated script in review console
python run.py --review-scripts

# Check script voiceover for "tu" usage (not "voi")
# Example: "ti mostro" ✅   vs   "vi mostro" ❌
```

---

### **Test 3: Voice Configuration**

```bash
# Generate assets with gym_fitness_pro workspace
# (assuming script approved in Gate 1)
python run.py --produce-assets <script_id>
```

**Expected Behavior**:
1. TTS Service logs: `"Workspace voice config: Voice model: nova, Speed: 1.1"`
2. Generated voiceover uses "nova" voice (energetic, friendly)
3. Playback speed 1.1x (10% faster than normal)

**Validation**:
Listen to generated voiceover:
```bash
# Find voiceover file in output
ls -la output/*/voiceover.mp3

# Play and verify voice sounds energetic (nova) and slightly faster
```

---

### **Test 4: Tone of Address Validation**

Create a test script with wrong tone:

**Scenario**: gym_fitness_pro expects `"tu_informale"`, but script uses `"voi_formale"`

```python
# Manual test in Python console
from yt_autopilot.agents.quality_reviewer import _check_narrator_persona_consistency
from yt_autopilot.core.schemas import VideoScript

# Test script with "voi" tone
script = VideoScript(
    hook="Oggi vi mostro gli squat perfetti",  # ❌ Uses "vi"
    bullets=["Tip 1", "Tip 2"],
    outro_cta="Iscrivetevi!",
    full_voiceover_text="Oggi vi mostro gli squat perfetti. Vi spiego la tecnica corretta. Iscrivetevi!",
    scene_voiceover_map=[]
)

narrator_config = {
    "enabled": True,
    "tone_of_address": "tu_informale"  # Expects "tu", not "voi"
}

# Should FAIL
is_consistent, reason = _check_narrator_persona_consistency(script, narrator_config)
print(f"Consistent: {is_consistent}")
print(f"Reason: {reason}")
# Expected: Consistent: False
# Expected: Reason: "Script uses formal 'voi' ('vi mostro') but workspace requires 'tu informale'..."
```

---

### **Test 5: Backward Compatibility**

Test that workspaces with `narrator_persona.enabled = false` still work:

```bash
# Switch to tech_ai_creator (narrator disabled)
python run.py --switch-workspace tech_ai_creator

# Generate script
python run.py --generate-script "2025-01-27T18:00:00"
```

**Expected Behavior**:
1. ScriptWriter does NOT log narrator persona info
2. Script generated with default logic (no narrator name, no signature phrases)
3. TTS uses default voice config (`alloy` @ 1.05 speed)
4. Quality Reviewer skips narrator persona check

---

## 📊 Expected Impact

### **Metrics to Track** (Before vs After)

| Metric | Before (No Narrator) | After (With Narrator) | Target Improvement |
|--------|---------------------|-----------------------|-------------------|
| Average Watch Time | ~35-40% | 50-60% | +20-30% |
| Brand Recognition | Low (generic) | High (Coach Marco) | 70%+ identify channel |
| Voice Consistency | Random (same voice all workspaces) | Unique per workspace | 100% consistent |
| Sponsor Interest | Low (no identity) | High (clear brand) | First deal in 3 months |

### **Key Success Indicators**

✅ **Retention**: Comments like "Coach Marco is back!", "Love this voice!", "Signature phrase became a meme"

✅ **Brand Recall**: Audience can identify channel without seeing logo/title

✅ **Multi-Workspace Growth**: Each workspace develops distinct fanbase

✅ **Sponsorship**: Sponsors want to sponsor "Coach Marco's fitness channel" (not just "a fitness channel")

---

## 🚀 Next Steps: Phase 2 & 3 (Future)

### **Phase 2: Visual Brand Manual** (Not Yet Implemented)

- Color palette enforcement in Veo prompts
- Logo overlay in video assembly
- Lower thirds with narrator name
- Typography customization

### **Phase 3: Visual Contexts** (Not Yet Implemented)

- Recurring visual scenarios per format (e.g., "home gym" for tutorials)
- Pattern recognition boost for retention
- Context-aware scene generation

### **Phase 4: Advanced Features** (Optional)

- ElevenLabs voice cloning integration
- Branded intro/outro animations
- Advanced typography with custom fonts
- Multi-language narrator variants

---

## 📝 Developer Notes

### **Architecture Decisions**

1. **Format-First Principle**: Video format drives structure, narrator persona provides tone
   - Ensures content optimization > rigid branding
   - LLM has creative freedom to adapt persona appropriately

2. **Backward Compatibility**: All new fields optional
   - Workspaces without narrator persona continue working
   - Gradual migration path (enable per workspace)

3. **No Rigid Template Enforcement**: Quality Reviewer validates consistency, not presence
   - Tone of address checked ✅
   - Signature phrases NOT enforced ✅
   - Agent decides when to use signature phrases

### **Integration Points**

- **Pipeline → ScriptWriter**: Pass workspace config to access narrator_persona
- **Pipeline → TTS Service**: Pass workspace_config for voice_config
- **Pipeline → Quality Reviewer**: Pass workspace (memory) for narrator validation

### **Future Enhancements**

- [ ] Pipeline update to use `_build_persona_aware_prompt()` for LLM calls
- [ ] Analytics tracking: narrator persona usage correlation with retention
- [ ] A/B testing framework: narrator ON vs OFF per workspace

---

## 🐛 Troubleshooting

### **Issue**: Script still uses "voi" when "tu_informale" is configured

**Cause**: LLM generates script before narrator persona integration (pipeline not updated)

**Solution**: Currently, `_build_persona_aware_prompt()` is available but not yet called by pipeline. Manual script review at Gate 1 required.

**Future Fix**: Update `build_video_package.py` to call LLM with narrator-aware prompt.

---

### **Issue**: Voice sounds the same across all workspaces

**Cause**: Pipeline not passing `workspace_config` to TTS service

**Solution**: Verify pipeline updated at line ~313:
```python
voiceover_path = synthesize_voiceover(
    ready.script,
    asset_paths,
    workspace_config=workspace_config  # ← Must be present
)
```

---

### **Issue**: Quality Reviewer rejects script for missing signature phrase

**Cause**: Incorrect implementation (should NOT enforce signature phrases)

**Solution**: Verify `_check_narrator_persona_consistency()` has this comment:
```python
# NOTE: We do NOT enforce rigid signature phrase presence
# Format determines if signature phrases are appropriate, not quality reviewer
```

---

## ✅ Implementation Checklist

- [x] Workspace schema extended (all 4 workspaces)
- [x] `narrator_persona` fields added
- [x] `voice_config` fields added
- [x] `content_formula` fields added
- [x] ScriptWriter `_build_persona_aware_prompt()` implemented
- [x] TTS Service workspace voice config integration
- [x] Quality Reviewer narrator consistency validation
- [x] Pipeline TTS call updated with workspace_config
- [x] Backward compatibility maintained
- [ ] Pipeline LLM call integration (future)
- [ ] Visual Brand Manual (Phase 2 - future)
- [ ] Visual Contexts (Phase 3 - future)

---

## 📚 Related Documentation

- `README.md`: Overall project documentation
- `ARCHITECTURE.md`: System architecture and layering
- `SERIES_FORMAT_ENGINE.md`: Format-based content structuring
- `STEP_08_*.md`: Trend selection enhancements

---

**End of Step 09 Documentation**
