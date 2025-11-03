"""
Config Migrator - Separazione AI Authority vs Strategic Config

Migra workspace configs da legacy hardcoded a AI-driven model.
Mantiene solo STRATEGIC parameters nel config (brand identity, tone, language).
Rimuove TACTICAL parameters che devono essere decisi da AI agents (format, duration, bullets).

Architecture Principles:
- Config = Brand Identity (strategic, immutable)
- AI Agents = Tactical Decisions (per-video, adaptive)

Author: YT Autopilot Team
Version: 2.0 (AI-Driven Config Authority)
"""

from typing import Dict, List, Tuple, Any, Optional
from copy import deepcopy
import logging

logger = logging.getLogger(__name__)


class ConfigMigrator:
    """
    Migra workspace config da legacy hardcoded a AI-driven.
    Mantiene solo STRATEGIC parameters nel config.

    Usage:
        migrator = ConfigMigrator()
        cleaned, hints = migrator.migrate_to_ai_driven(workspace)
    """

    # Tactical params che NON devono essere in config (AI authority)
    DEPRECATED_TACTICAL_PARAMS = [
        'video_style_mode.use_single_long_video',
        'content_formula.format_type',
        'content_formula.target_duration_seconds',
        'content_formula.bullets_count',
        'content_formula.min_bullets',
        'content_formula.max_bullets'
    ]

    # Strategic params che DEVONO rimanere in config
    STRATEGIC_PARAMS = [
        'workspace_name',
        'workspace_id',
        'vertical_id',
        'brand_tone',
        'target_language',
        'narrator_persona',
        'visual_brand_manual',
        'recent_titles',
        'trend_sources'
    ]

    # AI agents responsabili per tactical decisions
    AI_DECISION_MAKERS = {
        'format': 'Editorial Strategist',
        'duration': 'Duration Strategist + Format Reconciler',
        'aspect_ratio': 'Format Validator (derived from duration)',
        'bullets_count': 'Content Depth Strategist',
        'cta_type': 'CTA Strategist',
        'serie_concept': 'Editorial Strategist',
        'video_style_mode': 'Format Validator + Duration Strategist'
    }

    def __init__(self):
        self.migration_report = []

    def audit_workspace_config(self, workspace: Dict) -> Dict[str, List[Any]]:
        """
        Audit config per identificare legacy hardcoded parameters.

        Returns:
            Dict con findings:
                - strategic: Lista strategic params trovati (OK)
                - tactical_found: Lista tactical params che dovrebbero essere AI-driven
                - deprecated: Lista deprecated params da rimuovere
        """
        findings = {
            'strategic': [],
            'tactical_found': [],
            'deprecated': []
        }

        # Check for strategic params (OK)
        for param in self.STRATEGIC_PARAMS:
            if self._config_has_path(workspace, param):
                findings['strategic'].append(param)

        # Check for deprecated tactical params (BAD)
        for param_path in self.DEPRECATED_TACTICAL_PARAMS:
            if self._config_has_path(workspace, param_path):
                value = self._get_nested_value(workspace, param_path)
                findings['deprecated'].append({
                    'param': param_path,
                    'current_value': value,
                    'issue': f"Tactical param '{param_path}' should be decided by AI"
                })
                logger.warning(f"⚠️ Deprecated config found: {param_path} = {value}")

        # Check for tactical params in general
        tactical_params_map = {
            'content_formula.format_type': 'Editorial Strategist',
            'content_formula.target_duration_seconds': 'Duration Strategist',
            'content_formula.bullets_count': 'Content Depth Strategist',
            'video_style_mode.use_single_long_video': 'Format Validator'
        }

        for param_path, ai_owner in tactical_params_map.items():
            if self._config_has_path(workspace, param_path):
                value = self._get_nested_value(workspace, param_path)
                findings['tactical_found'].append({
                    'param': param_path,
                    'current_value': value,
                    'should_be_decided_by': ai_owner
                })

        # Summary
        logger.info(f"Config Audit Results:")
        logger.info(f"  ✅ Strategic params: {len(findings['strategic'])}")
        logger.info(f"  ⚠️ Tactical params found: {len(findings['tactical_found'])}")
        logger.info(f"  ❌ Deprecated params: {len(findings['deprecated'])}")

        return findings

    def migrate_to_ai_driven(
        self,
        workspace: Dict,
        preserve_hints: bool = True
    ) -> Tuple[Dict, Dict]:
        """
        Migra config da legacy a AI-driven.

        Args:
            workspace: Original workspace config
            preserve_hints: Se True, estrae hints da deprecated values (non vincolanti)

        Returns:
            Tuple[cleaned_config, migration_hints]
                - cleaned_config: Config con solo STRATEGIC params
                - migration_hints: Hints opzionali per AI agents (non vincolanti)
        """
        logger.info("=" * 70)
        logger.info("CONFIG MIGRATION: Legacy → AI-Driven")
        logger.info("=" * 70)

        cleaned = deepcopy(workspace)
        migration_hints = {}

        # Extract hints from deprecated params before removing
        if preserve_hints and 'content_formula' in workspace:
            formula = workspace['content_formula']

            # Convert legacy format_type to AI hint (not constraint)
            if 'format_type' in formula:
                migration_hints['preferred_format_hint'] = formula['format_type']
                migration_hints['hint_source'] = 'legacy_config'
                logger.info(f"  📝 Extracted format hint: '{formula['format_type']}' (AI can override)")

            # Convert legacy duration to AI preference range (not fixed value)
            if 'target_duration_seconds' in formula:
                legacy_duration = formula['target_duration_seconds']
                migration_hints['duration_preference_range'] = {
                    'min': int(legacy_duration * 0.5),
                    'max': int(legacy_duration * 2.0),
                    'legacy_value': legacy_duration,
                    'note': 'AI should decide optimal within this flexible range'
                }
                logger.info(f"  📝 Extracted duration preference: {legacy_duration}s → range [{int(legacy_duration*0.5)}-{int(legacy_duration*2.0)}s] (flexible)")

            # Convert legacy bullets count to hint
            if 'bullets_count' in formula or 'min_bullets' in formula:
                bullets_hint = formula.get('bullets_count', formula.get('min_bullets', 3))
                migration_hints['bullets_count_hint'] = {
                    'legacy_value': bullets_hint,
                    'note': 'Content Depth Strategist decides actual count based on duration + topic'
                }
                logger.info(f"  📝 Extracted bullets hint: {bullets_hint} (AI decides actual count)")

        # Extract video style hints
        if preserve_hints and 'video_style_mode' in workspace:
            style_mode = workspace['video_style_mode']
            if 'use_single_long_video' in style_mode:
                migration_hints['video_style_preference'] = {
                    'legacy_use_single_long': style_mode['use_single_long_video'],
                    'note': 'Format Validator decides based on AI-determined duration'
                }
                logger.info(f"  📝 Extracted video style hint: use_single_long={style_mode['use_single_long_video']} (AI decides based on duration)")

        # Remove deprecated tactical params
        params_removed = []

        if 'content_formula' in cleaned:
            formula = cleaned['content_formula']
            for key in ['format_type', 'target_duration_seconds', 'bullets_count', 'min_bullets', 'max_bullets']:
                if key in formula:
                    formula.pop(key)
                    params_removed.append(f'content_formula.{key}')

            # If content_formula is now empty, remove it entirely
            if not formula or formula == {}:
                cleaned.pop('content_formula')
                logger.info("  🗑️  Removed empty content_formula section")

        if 'video_style_mode' in cleaned:
            style_mode = cleaned['video_style_mode']
            if 'use_single_long_video' in style_mode:
                style_mode.pop('use_single_long_video')
                params_removed.append('video_style_mode.use_single_long_video')

            # If video_style_mode is now empty, remove it entirely
            if not style_mode or style_mode == {}:
                cleaned.pop('video_style_mode')
                logger.info("  🗑️  Removed empty video_style_mode section")

        logger.info(f"  ✅ Removed {len(params_removed)} tactical params:")
        for param in params_removed:
            logger.info(f"     - {param}")

        # Add AI authority notice
        cleaned['_ai_authority_notice'] = {
            'version': '2.0',
            'note': 'Format, duration, bullets count are decided by AI agents. Config contains only strategic brand parameters.',
            'ai_agents': list(self.AI_DECISION_MAKERS.values()),
            'decisions': self.AI_DECISION_MAKERS
        }

        # Add migration hints if any extracted
        if migration_hints and preserve_hints:
            cleaned['_migration_hints'] = migration_hints
            cleaned['_migration_hints']['notice'] = 'These are HINTS from legacy config, not constraints. AI can override.'

        logger.info("=" * 70)
        logger.info("✅ MIGRATION COMPLETE")
        logger.info(f"  Config now contains only STRATEGIC params")
        logger.info(f"  AI agents have full authority on tactical decisions")
        if migration_hints:
            logger.info(f"  Extracted {len(migration_hints)} optional hints for AI")
        logger.info("=" * 70)

        return cleaned, migration_hints

    def validate_migration(self, cleaned_config: Dict) -> Tuple[bool, List[str]]:
        """
        Valida che migration sia completa (nessun tactical param rimasto).

        Returns:
            Tuple[is_valid, violations]
        """
        violations = []

        for param_path in self.DEPRECATED_TACTICAL_PARAMS:
            # Skip _migration_hints (they're OK, just hints)
            if param_path.startswith('_'):
                continue

            if self._config_has_path(cleaned_config, param_path):
                value = self._get_nested_value(cleaned_config, param_path)
                violations.append(
                    f"❌ Tactical param still present: '{param_path}' = {value}"
                )

        # Check for AI authority notice
        if '_ai_authority_notice' not in cleaned_config:
            violations.append("❌ Missing '_ai_authority_notice' section")

        if violations:
            logger.error("Migration validation FAILED:")
            for v in violations:
                logger.error(f"  {v}")
            return False, violations

        logger.info("✅ Migration validation PASSED - Config is AI-driven compliant")
        return True, []

    # Helper methods

    def _config_has_path(self, config: Dict, path: str) -> bool:
        """Check if nested path exists in config (e.g., 'content_formula.format_type')."""
        keys = path.split('.')
        current = config

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]

        return True

    def _get_nested_value(self, config: Dict, path: str) -> Any:
        """Get value from nested path (e.g., 'content_formula.format_type')."""
        keys = path.split('.')
        current = config

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]

        return current

    def _set_nested_value(self, config: Dict, path: str, value: Any) -> None:
        """Set value at nested path (e.g., 'content_formula.format_type')."""
        keys = path.split('.')
        current = config

        for i, key in enumerate(keys[:-1]):
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value


def migrate_workspace_file(workspace_path: str, backup: bool = True) -> Tuple[bool, str]:
    """
    Convenience function per migrare un workspace file direttamente.

    Args:
        workspace_path: Path al workspace JSON file
        backup: Se True, crea backup prima di modificare

    Returns:
        Tuple[success, message]
    """
    import json
    from pathlib import Path

    try:
        # Load workspace
        with open(workspace_path, 'r', encoding='utf-8') as f:
            workspace = json.load(f)

        workspace_id = workspace.get('workspace_id', 'unknown')
        logger.info(f"\n📦 Migrating workspace: {workspace_id}")

        # Backup if requested
        if backup:
            backup_path = Path(workspace_path).with_suffix('.json.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(workspace, f, indent=2, ensure_ascii=False)
            logger.info(f"  💾 Backup saved: {backup_path}")

        # Migrate
        migrator = ConfigMigrator()
        cleaned, hints = migrator.migrate_to_ai_driven(workspace, preserve_hints=True)

        # Validate
        is_valid, violations = migrator.validate_migration(cleaned)
        if not is_valid:
            return False, f"Migration validation failed: {violations}"

        # Save cleaned config
        with open(workspace_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)

        logger.info(f"  ✅ Migrated config saved: {workspace_path}")

        return True, f"Successfully migrated {workspace_id}"

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False, str(e)


# Example usage
if __name__ == '__main__':
    import json

    # Example workspace config (legacy)
    legacy_config = {
        "workspace_id": "tech_ai_creator",
        "workspace_name": "Tech & AI Creator",
        "vertical_id": "tech_ai",
        "target_language": "en",
        "brand_tone": "Positivo, energico, educativo",
        "content_formula": {
            "format_type": "tutorial",  # ← TACTICAL (should be AI-driven)
            "target_duration_seconds": 60,  # ← TACTICAL
            "bullets_count": 3  # ← TACTICAL
        },
        "video_style_mode": {
            "type": "character_based",
            "use_single_long_video": True  # ← TACTICAL
        }
    }

    # Migrate
    migrator = ConfigMigrator()

    print("\n" + "=" * 70)
    print("DEMO: Config Migration")
    print("=" * 70)

    # Audit
    print("\n1. AUDIT LEGACY CONFIG")
    findings = migrator.audit_workspace_config(legacy_config)
    print(f"   Strategic params: {len(findings['strategic'])}")
    print(f"   Tactical found: {len(findings['tactical_found'])}")
    print(f"   Deprecated: {len(findings['deprecated'])}")

    # Migrate
    print("\n2. MIGRATE TO AI-DRIVEN")
    cleaned, hints = migrator.migrate_to_ai_driven(legacy_config)

    # Validate
    print("\n3. VALIDATE MIGRATION")
    is_valid, violations = migrator.validate_migration(cleaned)

    # Show results
    print("\n4. RESULTS")
    print("   CLEANED CONFIG:")
    print(json.dumps(cleaned, indent=2))
    print("\n   MIGRATION HINTS (optional for AI):")
    print(json.dumps(hints, indent=2))
