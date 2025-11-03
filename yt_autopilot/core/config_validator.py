"""
Config Validator - AI Authority Enforcement

Valida che workspace config contenga solo STRATEGIC parameters.
Blocks tactical params che dovrebbero essere decisi da AI agents.

Questo validator viene chiamato all'inizio della pipeline per garantire
che config legacy hardcoded non interferisca con AI reasoning.

Architecture Principles:
- Config = Brand Identity (strategic, immutable)
- AI Agents = Tactical Decisions (per-video, adaptive)

Author: YT Autopilot Team
Version: 2.0 (AI-Driven Config Authority)
"""

from typing import Dict, List, Tuple, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Valida che config contenga solo STRATEGIC params.
    Blocks tactical params che dovrebbero essere AI-driven.

    Usage:
        validator = ConfigValidator()
        is_valid, violations = validator.validate_config_authority(workspace)
        if not is_valid:
            # Config needs migration
    """

    # Tactical params che NON devono essere in config (AI authority)
    FORBIDDEN_TACTICAL_PARAMS = [
        'content_formula.format_type',
        'content_formula.target_duration_seconds',
        'content_formula.bullets_count',
        'content_formula.min_bullets',
        'content_formula.max_bullets',
        'video_style_mode.use_single_long_video'
    ]

    # Strategic params richiesti
    REQUIRED_STRATEGIC_PARAMS = [
        'workspace_id',
        'workspace_name',
        'vertical_id',
        'target_language',
        'brand_tone'
    ]

    # Optional strategic params (raccomandati ma non required)
    OPTIONAL_STRATEGIC_PARAMS = [
        'narrator_persona',
        'visual_brand_manual',
        'recent_titles',
        'trend_sources',
        '_ai_authority_notice',
        '_migration_hints'
    ]

    def __init__(self, strict_mode: bool = False):
        """
        Args:
            strict_mode: Se True, valida anche required params (più restrittivo)
        """
        self.strict_mode = strict_mode

    def validate_config_authority(
        self,
        workspace: Dict,
        auto_suggest_migration: bool = True
    ) -> Tuple[bool, List[str]]:
        """
        Valida che config non contenga tactical overrides.

        Args:
            workspace: Workspace config da validare
            auto_suggest_migration: Se True, suggerisce come fixare violations

        Returns:
            Tuple[is_valid, violations]
                - is_valid: True se config è AI-driven compliant
                - violations: Lista violations trovati
        """
        violations = []
        workspace_id = workspace.get('workspace_id', 'unknown')

        logger.info("=" * 70)
        logger.info(f"CONFIG VALIDATION: {workspace_id}")
        logger.info("=" * 70)

        # Check 1: Forbidden tactical params
        for forbidden_path in self.FORBIDDEN_TACTICAL_PARAMS:
            if self._config_has_path(workspace, forbidden_path):
                value = self._get_nested_value(workspace, forbidden_path)
                ai_owner = self._get_ai_owner(forbidden_path)

                violation = (
                    f"❌ FORBIDDEN: Config contains tactical param '{forbidden_path}' = {value}. "
                    f"This should be decided by {ai_owner}."
                )
                violations.append(violation)
                logger.error(f"  {violation}")

        # Check 2: Required strategic params
        if self.strict_mode:
            for required_path in self.REQUIRED_STRATEGIC_PARAMS:
                if not self._config_has_path(workspace, required_path):
                    violation = f"❌ MISSING: Required strategic param '{required_path}' not found"
                    violations.append(violation)
                    logger.error(f"  {violation}")

        # Check 3: AI authority notice (recommended)
        if '_ai_authority_notice' not in workspace:
            warning = "⚠️ WARNING: Missing '_ai_authority_notice' section (recommended but not required)"
            logger.warning(f"  {warning}")
            # Not a violation, just a warning

        # Summary
        if violations:
            logger.error("=" * 70)
            logger.error(f"❌ VALIDATION FAILED: {len(violations)} violations found")
            logger.error("=" * 70)

            if auto_suggest_migration:
                logger.info("\n💡 FIX: Use ConfigMigrator to clean config:")
                logger.info("    from yt_autopilot.core.config_migrator import ConfigMigrator")
                logger.info("    migrator = ConfigMigrator()")
                logger.info("    cleaned, hints = migrator.migrate_to_ai_driven(workspace)")
                logger.info("")

            return False, violations
        else:
            logger.info("=" * 70)
            logger.info("✅ VALIDATION PASSED: Config is AI-driven compliant")
            logger.info("=" * 70)
            return True, []

    def validate_and_enforce(
        self,
        workspace: Dict,
        auto_migrate: bool = False
    ) -> Tuple[Dict, bool, List[str]]:
        """
        Valida config e opzionalmente auto-migrate se violations trovati.

        Args:
            workspace: Workspace config da validare
            auto_migrate: Se True, applica auto-migration se validation fails

        Returns:
            Tuple[workspace, is_valid, violations]
                - workspace: Config (migrato se auto_migrate=True e violations trovati)
                - is_valid: True se validation passed
                - violations: Lista violations (vuota se valid o auto-migrato)
        """
        is_valid, violations = self.validate_config_authority(workspace, auto_suggest_migration=False)

        if not is_valid and auto_migrate:
            logger.warning("⚠️ Config validation failed, attempting auto-migration...")

            from yt_autopilot.core.config_migrator import ConfigMigrator

            migrator = ConfigMigrator()
            cleaned, hints = migrator.migrate_to_ai_driven(workspace, preserve_hints=True)

            # Re-validate cleaned config
            is_valid_after, violations_after = self.validate_config_authority(cleaned, auto_suggest_migration=False)

            if is_valid_after:
                logger.info("✅ Auto-migration successful, config is now AI-driven compliant")
                return cleaned, True, []
            else:
                logger.error("❌ Auto-migration failed, manual intervention required")
                return workspace, False, violations_after

        return workspace, is_valid, violations

    def check_tactical_param_usage(
        self,
        workspace: Dict,
        param_path: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check se un tactical param specifico è usato nel config (per debugging).

        Args:
            workspace: Workspace config
            param_path: Path del param (e.g., 'content_formula.format_type')

        Returns:
            Tuple[is_used, warning_message]
        """
        if self._config_has_path(workspace, param_path):
            value = self._get_nested_value(workspace, param_path)
            ai_owner = self._get_ai_owner(param_path)

            warning = (
                f"⚠️ Tactical param '{param_path}' = {value} found in config. "
                f"This should be decided by {ai_owner}. "
                f"AI agents may be constrained by this hardcoded value."
            )
            return True, warning

        return False, None

    # Helper methods

    def _config_has_path(self, config: Dict, path: str) -> bool:
        """Check if nested path exists in config."""
        keys = path.split('.')
        current = config

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return False
            current = current[key]

        return True

    def _get_nested_value(self, config: Dict, path: str) -> Any:
        """Get value from nested path."""
        keys = path.split('.')
        current = config

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]

        return current

    def _get_ai_owner(self, param_path: str) -> str:
        """Get AI agent responsabile per quel param."""
        ai_owners = {
            'content_formula.format_type': 'Editorial Strategist',
            'content_formula.target_duration_seconds': 'Duration Strategist + Format Reconciler',
            'content_formula.bullets_count': 'Content Depth Strategist',
            'content_formula.min_bullets': 'Content Depth Strategist',
            'content_formula.max_bullets': 'Content Depth Strategist',
            'video_style_mode.use_single_long_video': 'Format Validator + Duration Strategist'
        }
        return ai_owners.get(param_path, 'AI Agent')


class ConfigAuthorityEnforcer:
    """
    Pipeline integration helper per enforce config authority.
    Chiamato all'inizio della pipeline per validare workspace config.

    Usage in pipeline:
        enforcer = ConfigAuthorityEnforcer()
        workspace, is_valid = enforcer.enforce_at_pipeline_start(workspace)
        if not is_valid:
            # Pipeline cannot proceed with confidence
    """

    def __init__(self, auto_migrate: bool = True, strict_mode: bool = False):
        """
        Args:
            auto_migrate: Se True, auto-migrate config se violations trovati
            strict_mode: Se True, require anche required strategic params
        """
        self.validator = ConfigValidator(strict_mode=strict_mode)
        self.auto_migrate = auto_migrate

    def enforce_at_pipeline_start(
        self,
        workspace: Dict,
        workspace_id: str
    ) -> Tuple[Dict, bool]:
        """
        Enforce config authority all'inizio della pipeline.

        Args:
            workspace: Workspace config loaded
            workspace_id: Workspace ID per logging

        Returns:
            Tuple[workspace, is_valid]
                - workspace: Config (possibilmente migrato)
                - is_valid: True se config è AI-driven compliant
        """
        logger.info("")
        logger.info("🔒 CONFIG AUTHORITY ENFORCEMENT")
        logger.info(f"   Workspace: {workspace_id}")
        logger.info(f"   Auto-migrate: {self.auto_migrate}")
        logger.info("")

        workspace, is_valid, violations = self.validator.validate_and_enforce(
            workspace,
            auto_migrate=self.auto_migrate
        )

        if not is_valid:
            logger.error("=" * 70)
            logger.error("❌ CONFIG VALIDATION FAILED")
            logger.error("=" * 70)
            logger.error("AI agents cannot operate with full authority.")
            logger.error("Config contains tactical overrides that constrain AI reasoning.")
            logger.error("")
            logger.error("Violations:")
            for v in violations:
                logger.error(f"  {v}")
            logger.error("")
            logger.error("💡 SOLUTION: Run migration manually:")
            logger.error("  python3 -c \"from yt_autopilot.core.config_migrator import migrate_workspace_file; migrate_workspace_file('workspaces/{workspace_id}.json')\"")
            logger.error("=" * 70)

            if not self.auto_migrate:
                raise ValueError(
                    f"Config validation failed for workspace '{workspace_id}'. "
                    f"Run migration or enable auto_migrate=True."
                )

        return workspace, is_valid

    def validate_config_file(self, config_path: str) -> Tuple[bool, List[str]]:
        """
        Convenience method per validare un config file direttamente.

        Args:
            config_path: Path al workspace JSON file

        Returns:
            Tuple[is_valid, violations]
        """
        import json

        with open(config_path, 'r', encoding='utf-8') as f:
            workspace = json.load(f)

        workspace_id = workspace.get('workspace_id', 'unknown')
        logger.info(f"Validating config file: {config_path} ({workspace_id})")

        is_valid, violations = self.validator.validate_config_authority(workspace)
        return is_valid, violations


# Example usage
if __name__ == '__main__':
    import json

    # Example 1: Valid AI-driven config
    valid_config = {
        "workspace_id": "tech_ai_creator",
        "workspace_name": "Tech & AI Creator",
        "vertical_id": "tech_ai",
        "target_language": "en",
        "brand_tone": "Positivo, energico, educativo",
        "_ai_authority_notice": {
            "version": "2.0",
            "note": "AI agents have full authority on tactical decisions"
        }
    }

    # Example 2: Invalid legacy config with tactical params
    invalid_config = {
        "workspace_id": "tech_ai_creator",
        "workspace_name": "Tech & AI Creator",
        "vertical_id": "tech_ai",
        "target_language": "en",
        "brand_tone": "Positivo, energico, educativo",
        "content_formula": {
            "format_type": "tutorial",  # ← TACTICAL (forbidden!)
            "target_duration_seconds": 60  # ← TACTICAL (forbidden!)
        }
    }

    print("\n" + "=" * 70)
    print("DEMO: Config Validation")
    print("=" * 70)

    validator = ConfigValidator()

    # Test 1: Valid config
    print("\n1. VALID CONFIG (AI-driven)")
    is_valid, violations = validator.validate_config_authority(valid_config)
    print(f"   Result: {'PASS' if is_valid else 'FAIL'}")

    # Test 2: Invalid config
    print("\n2. INVALID CONFIG (Legacy with tactical params)")
    is_valid, violations = validator.validate_config_authority(invalid_config)
    print(f"   Result: {'PASS' if is_valid else 'FAIL'}")
    print(f"   Violations: {len(violations)}")

    # Test 3: Auto-migration
    print("\n3. AUTO-MIGRATION TEST")
    cleaned, is_valid, violations = validator.validate_and_enforce(
        invalid_config,
        auto_migrate=True
    )
    print(f"   Result after migration: {'PASS' if is_valid else 'FAIL'}")
    print(f"   Cleaned config has tactical params: {validator._config_has_path(cleaned, 'content_formula.format_type')}")
