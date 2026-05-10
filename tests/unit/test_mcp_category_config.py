from __future__ import annotations

from pathlib import Path

from radar.analyzer import apply_entity_rules
from radar.collector import parse_markdown_section_items
from radar.config_loader import load_category_config, load_category_quality_config
from radar.models import Article


def _category_name() -> str:
    configs = sorted(Path("config/categories").glob("*.yaml"))
    assert len(configs) == 1
    return configs[0].stem


def _seed_source(category):
    seeds = [source for source in category.sources if source.type == "github_readme_section"]
    assert len(seeds) == 1
    return seeds[0]


def _mcp_source(category, repository: str):
    return next(
        source
        for source in category.sources
        if source.type == "mcp_server" and source.config.get("repository") == repository
    )


def test_mcp_category_config_uses_readme_section_source() -> None:
    category = load_category_config(_category_name())

    source = _seed_source(category)
    assert source.type == "github_readme_section"
    assert source.url == "https://raw.githubusercontent.com/darjeeling/awesome-mcp-korea/main/README.md"
    assert source.section
    assert source.trust_tier == "T4_community"
    assert source.collection_tier == "C1_static_list"
    assert source.content_type == "mcp_directory"
    assert {entity.name for entity in category.entities} >= {
        "MCPDomain",
        "Provider",
        "Capability",
        "RiskScope",
        "ProjectHealth",
    }


def test_mcp_category_config_matches_section_entries() -> None:
    category = load_category_config(_category_name())
    seed_source = _seed_source(category)
    section = seed_source.section
    markdown = f"""
### {section}

**[example-mcp](https://github.com/example/example-mcp)** - {section} MCP server with API search tools.

### Other Section

**[other-mcp](https://github.com/example/other-mcp)** - Another MCP server.
"""

    items = parse_markdown_section_items(markdown, section)
    assert len(items) == 1

    article = Article(
        title=items[0]["title"],
        link=items[0]["link"],
        summary=items[0]["summary"],
        source=seed_source.name,
        category=category.category_name,
    )
    analyzed = apply_entity_rules([article], category.entities)

    assert analyzed[0].matched_entities
    assert "MCPDomain" in analyzed[0].matched_entities
    assert "ProjectHealth" in analyzed[0].matched_entities


def test_mcp_server_sources_are_disabled_metadata_candidates() -> None:
    category = load_category_config(_category_name())
    candidates = [source for source in category.sources if source.type == "mcp_server"]
    if category.category_name != "misc_mcp":
        assert candidates

    allowed_statuses = {
        "metadata_only",
        "blocked_command_unresolved",
        "blocked_env_required",
        "blocked_tool_allowlist_unresolved",
        "candidate_ready_for_fake_transport_test",
        "fake_transport_smoke_test_passed",
        "real_transport_smoke_test_passed",
    }
    for source in candidates:
        controlled_rollout_enabled = (
            source.config.get("production_enablement_status") == "controlled_rollout_enabled"
        )
        assert source.collection_tier == "C4_mcp_tool"
        assert source.content_type == "mcp_tool_result"
        assert source.config["activation_status"] in allowed_statuses
        assert source.config["repository"]
        assert isinstance(source.config.get("tools", []), list)
        assert isinstance(source.config.get("resources", []), list)
        assert source.config["docs_advisory_audit_status"] == "passed"
        assert (
            source.config["docs_advisory_audit_artifact"]
            == "_workspace/2026-04-30_cycle69_mcp_docs_advisory_audit.json"
        )
        assert source.config["github_readme_present"] is True
        assert source.config["github_docs_present"] is True
        assert source.config["github_docs_paths"]
        assert source.config["github_security_advisory_access_status"].startswith("checked")
        assert source.config["github_security_advisory_count"] >= 0
        if source.config.get("command_discovery_status"):
            assert source.config["command_discovery_checked_at"]
            assert (
                source.config["command_discovery_artifact"]
                == "_workspace/2026-04-30_cycle71_mcp_command_discovery_audit.json"
            )
        if "command_or_endpoint_unresolved" in source.config.get("activation_gates", []):
            assert source.config["command_discovery_status"]
        if source.enabled:
            assert source.config["activation_status"] == "real_transport_smoke_test_passed"
            assert source.config["command"]
            assert source.config["tools"]
            assert "fake_transport_smoke_test_required" not in source.config["activation_gates"]
            if controlled_rollout_enabled:
                assert source.config["production_rollout_status"] == "active"
                assert source.config["activation_gates"] == []
        else:
            assert source.config["activation_status"] != "real_transport_smoke_test_passed"
        if source.config["activation_status"] != "metadata_only":
            assert source.config["activation_audited_at"]
            if controlled_rollout_enabled:
                assert source.config["activation_gates"] == []
            else:
                assert source.config["activation_gates"]


def test_ko_stdict_candidate_has_controlled_real_transport_rollout_metadata() -> None:
    category = load_category_config(_category_name())
    source = _mcp_source(category, "dahlia/ko-stdict-mcp")

    assert source.enabled is True
    assert source.config["activation_status"] == "real_transport_smoke_test_passed"
    assert source.config["real_transport_smoke_tested_at"] == "2026-05-08T05:05:11+00:00"
    assert source.config["real_transport_smoke_test_status"] == "passed"
    assert (
        source.config["real_transport_smoke_test_artifact"]
        == "_workspace/2026-05-08_kostdict_bounded_real_preflight_probe.json"
    )
    assert (
        source.config["real_transport_smoke_test_source"]
        == "bounded_real_transport_probe_dictionary_status"
    )
    assert "tool_allowlist_unresolved" not in source.config["risk_scope"]
    assert source.config["risk_scope"] == ["bulk_data_download", "local_file_write", "network_read"]
    assert source.config["package_registry"] == "jsr"
    assert source.config["package_registry_crosscheck_status"] == "passed"
    assert source.config["package_name"] == "@hongminhee/ko-stdict-mcp"
    assert source.config["package_version"] == "0.2.0"
    assert source.config["metadata_checked_at"] == "2026-05-07T05:20:56+00:00"
    assert source.config["metadata_refresh_status"] == "passed"
    assert (
        source.config["metadata_refresh_artifact"]
        == "_workspace/2026-05-07_mcp_github_repository_metadata_refresh.json"
    )
    assert source.config["metadata_refresh_source"] == "github_rest_api"
    assert source.config["github_stars"] == 23
    assert source.config["github_head_sha"] == "168f902bc8b820f4242812ed0af411a5e8918893"
    assert source.config["production_monitoring_status"] == "controlled_monitoring_active"
    assert (
        source.config["production_monitoring_artifact"]
        == "_workspace/2026-05-08_kostdict_real_transport_enablement_smoke.json"
    )
    assert source.config["production_monitoring_source"] == "controlled_real_transport_enablement_smoke"
    assert source.config["production_monitoring_activation_condition"] == (
        "source_enabled_after_ready_cache_and_bounded_dictionary_status_real_probe"
    )
    assert source.config["production_monitoring_rollout_scope"] == (
        "dictionary_status_only_ready_cache"
    )
    assert source.config["command_semantics"] == "npx_deno_eval_jsr_run_stdio_server"
    assert source.config["command_resolution_status"] == "resolved_via_npx_deno_eval"
    assert source.config["real_transport_entrypoint_review_status"] == (
        "package_root_import_exits_without_stdio"
    )
    assert (
        source.config["real_transport_entrypoint_review_artifact"]
        == "_workspace/2026-04-29_cycle52_kostdict_bounded_real_bootstrap_probe_rerun.json"
    )
    assert (
        source.config["real_transport_entrypoint_corrective_action"]
        == "call_exported_runStdioServer_via_deno_eval"
    )
    assert source.config["command"] == "npx"
    assert source.config["args"] == [
        "-y",
        "deno@2.7.14",
        "eval",
        'import { runStdioServer } from "jsr:@hongminhee/ko-stdict-mcp@0.2.0"; await runStdioServer();',
    ]
    assert source.config["env"] == {
        "NPM_CONFIG_CACHE": ".cache/mcp/ko-stdict-mcp/npm-cache",
        "DENO_DIR": ".cache/mcp/ko-stdict-mcp/deno-cache",
        "KO_STDICT_DATA_DIR": ".cache/mcp/ko-stdict-mcp/data",
    }
    assert source.config["tools"] == [{"name": "dictionary_status", "arguments": {}}]
    assert source.config["timeout_seconds"] == 300
    assert source.config["max_items"] == 1
    assert source.config["event_model"] == "mcp_tool_result"
    assert source.config["runtime_bootstrap_review_status"] == "bounded_preflight_policy_documented"
    assert (
        source.config["runtime_bootstrap_review_artifact"]
        == "_workspace/2026-04-29_cycle50_kostdict_bootstrap_review.json"
    )
    assert source.config["runtime_bootstrap_preflight_guard_status"] == "static_guard_enforced_in_probe"
    assert (
        source.config["runtime_bootstrap_preflight_guard_artifact"]
        == "_workspace/2026-04-29_cycle51_kostdict_bounded_preflight_dry_run.json"
    )
    assert source.config["bounded_real_bootstrap_previous_failure_status"] == (
        "failed_bootstrap_timeout"
    )
    assert (
        source.config["bounded_real_bootstrap_previous_failure_artifact"]
        == "_workspace/2026-04-29_cycle52_kostdict_eval_entrypoint_bounded_real_probe.json"
    )
    assert source.config["bounded_real_bootstrap_previous_timeout_seconds"] == 300
    assert source.config["bounded_real_bootstrap_previous_cache_status"] == "passed_within_limit"
    assert source.config["bounded_real_bootstrap_previous_cache_bytes"] == 677139214
    assert source.config["bounded_real_bootstrap_preflight_status"] == (
        "passed_ready_cache_dictionary_status"
    )
    assert (
        source.config["bounded_real_bootstrap_preflight_artifact"]
        == "_workspace/2026-05-08_kostdict_bounded_real_preflight_probe.json"
    )
    assert source.config["bounded_real_bootstrap_timeout_seconds"] == 300
    assert source.config["bounded_real_bootstrap_cache_status"] == "passed_within_limit"
    assert source.config["bounded_real_bootstrap_cache_bytes"] == 670190122
    assert source.config["bounded_real_bootstrap_tool_call"] == "dictionary_status"
    assert source.config["bounded_real_bootstrap_ready"] is True
    assert source.config["bounded_real_bootstrap_entry_count"] == 179500
    assert source.config["bounded_real_bootstrap_schema_version"] == 2
    assert source.config["real_transport_blocker"] == (
        "resolved_by_prebuilt_cache_ready_dictionary_status_preflight"
    )
    assert source.config["runtime_bootstrap_partial_cache_status"] == (
        "staging_cache_promoted_to_ready"
    )
    assert source.config["runtime_bootstrap_cache_readiness_status"] == "ready"
    assert (
        source.config["runtime_bootstrap_cache_readiness_artifact"]
        == "_workspace/2026-05-08_kostdict_post_enablement_cache_inspection.json"
    )
    assert source.config["runtime_bootstrap_cache_root_bytes"] == 214856662
    assert source.config["runtime_bootstrap_runtime_write_root_bytes"] == 421708276
    assert source.config["runtime_bootstrap_state_schema_version"] == 2
    assert source.config["runtime_bootstrap_ready_database_status"] == "ready"
    assert source.config["runtime_bootstrap_ready_database_bytes"] == 146161664
    assert source.config["runtime_bootstrap_ready_entry_count"] == 179500
    assert source.config["runtime_bootstrap_ready_sense_count"] == 209237
    assert source.config["runtime_bootstrap_ready_schema_version"] == 2
    assert (
        source.config["runtime_bootstrap_ready_source_filename"]
        == "전체 내려받기_표준국어대사전_JSON_20260306.zip"
    )
    assert source.config["runtime_bootstrap_ready_source_date"] == "2026-03-06"
    assert source.config["runtime_bootstrap_staging_entry_count"] == 179500
    assert source.config["runtime_bootstrap_staging_sense_count"] == 209237
    assert source.config["prebuilt_cache_promotion_status"] == "promoted"
    assert source.config["prebuilt_cache_promotion_mode"] == "metadata_only_repair"
    assert (
        source.config["prebuilt_cache_promotion_artifact"]
        == "_workspace/2026-05-08_kostdict_prebuilt_cache_promotion.json"
    )
    assert source.config["bootstrap_performance_review_status"] == (
        "bounded_real_transport_preflight_passed"
    )
    assert (
        source.config["bootstrap_performance_review_artifact"]
        == "_workspace/2026-05-08_kostdict_bounded_real_preflight_probe.json"
    )
    assert source.config["bootstrap_performance_review_decision"] == (
        "ready_cache_prevented_rebuild_dictionary_status_returned"
    )
    assert source.config["prebuilt_cache_strategy_status"] == "ready_cache_published"
    assert (
        source.config["prebuilt_cache_strategy_artifact"]
        == "_workspace/2026-05-08_kostdict_prebuilt_cache_promotion.json"
    )
    assert source.config["prebuilt_cache_strategy_decision"] == (
        "offline_staging_database_promoted_then_next_real_probe_allowed"
    )
    assert source.config["prebuilt_cache_acceptance_status"] == "ready"
    assert (
        source.config["prebuilt_cache_acceptance_artifact"]
        == "_workspace/2026-05-08_kostdict_post_enablement_cache_inspection.json"
    )
    assert source.config["prebuilt_cache_acceptance_blocker"] == "none"
    assert source.config["production_enablement_status"] == "controlled_rollout_enabled"
    assert source.config["production_enablement_decision_status"] == (
        "real_transport_smoke_passed_ready_cache"
    )
    assert source.config["production_enablement_decision_at"] == "2026-05-08T06:52:24+00:00"
    assert source.config["production_enablement_recommended_option"] == "controlled_enablement"
    assert source.config["production_enablement_source_enabled_after_decision"] is True
    assert source.config["production_enablement_decision_failed_checks"] == []
    assert source.config["production_rollout_status"] == "active"
    assert source.config["production_rollout_enabled_at"] == "2026-05-08T06:52:24+00:00"
    assert source.config["production_rollout_guarded_at"] == "2026-05-08T06:52:24+00:00"
    assert source.config["production_rollout_monitored_at"] == "2026-05-08T06:52:24+00:00"
    assert (
        source.config["production_rollout_monitor_artifact"]
        == "_workspace/2026-05-08_kostdict_real_transport_enablement_smoke.json"
    )
    assert source.config["production_monitoring_metrics"] == {
        "min_article_count": 1,
        "require_non_empty_summary_count_equals_article_count": True,
        "max_exact_fallback_link_count": 0,
        "max_duplicate_link_count": 0,
        "expected_source_name": "dahlia/ko-stdict-mcp",
        "expected_category": "korean_nlp_mcp",
        "expected_dictionary_status_ready": True,
        "expected_schema_version": 2,
    }
    assert "dictionary_status_not_ready" in source.config["production_rollback_criteria"]
    assert "schema_version_mismatch" in source.config["production_rollback_criteria"]
    assert source.config["production_collection_cadence"] == "controlled_low_frequency_rollout"
    policy = source.config["runtime_bootstrap_policy"]
    assert policy["execution_mode"] == "one_shot_real_transport_preflight"
    assert policy["allowed_tool_names"] == ["dictionary_status"]
    assert policy["disallowed_tool_names"] == ["refresh_dictionary", "search_entries", "get_entry"]
    assert policy["allowed_write_roots"] == [".cache/mcp/ko-stdict-mcp"]
    assert policy["data_dir_env"] == "KO_STDICT_DATA_DIR"
    assert policy["expected_download_url"] == "https://stdict.korean.go.kr/common/download.do"
    assert policy["required_env"] == {
        "NPM_CONFIG_CACHE": ".cache/mcp/ko-stdict-mcp/npm-cache",
        "DENO_DIR": ".cache/mcp/ko-stdict-mcp/deno-cache",
        "KO_STDICT_DATA_DIR": ".cache/mcp/ko-stdict-mcp/data",
    }
    assert policy["max_bootstrap_seconds"] == 300
    assert policy["max_cache_bytes"] == 1073741824
    assert policy["max_response_items"] == 1
    assert policy["require_ready_status"] is True
    assert policy["require_schema_version"] == 2
    assert policy["cleanup_policy"] == "keep_ready_cache_for_controlled_dictionary_status_rollout"
    cache_policy = source.config["runtime_bootstrap_cache_readiness_policy"]
    assert cache_policy["data_root"] == ".cache/mcp/ko-stdict-mcp/data"
    assert cache_policy["state_file"] == ".cache/mcp/ko-stdict-mcp/data/state.json"
    assert cache_policy["ready_database"] == ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite"
    assert cache_policy["staging_database"] == ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next"
    assert cache_policy["download_globs"] == [
        ".cache/mcp/ko-stdict-mcp/data/downloads/*.zip"
    ]
    assert cache_policy["required_schema_version"] == 2
    assert cache_policy["minimum_ready_database_bytes"] == 1
    assert cache_policy["inspect_sqlite_tables"] == ["entries", "senses", "metadata"]
    assert cache_policy["required_metadata_fields"] == [
        "schema_version",
        "source_filename",
        "source_date",
        "entry_count",
        "imported_at",
    ]
    assert cache_policy["require_state_download_matches_metadata"] is True
    assert cache_policy["partial_cache_indicators"] == [
        ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next",
        ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next-wal",
        ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next-shm",
    ]
    prebuilt_policy = source.config["runtime_bootstrap_prebuilt_cache_policy"]
    assert prebuilt_policy["strategy"] == "offline_build_then_atomic_cache_publish"
    assert prebuilt_policy["required_before_next_real_probe"] is True
    assert prebuilt_policy["offline_execution_boundary"] == (
        "run_dictionary_import_outside_mcp_stdio_startup"
    )
    assert prebuilt_policy["accepted_cache_readiness_status"] == "ready"
    assert prebuilt_policy["ready_state_schema_version"] == 2
    assert prebuilt_policy["ready_database"] == ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite"
    assert prebuilt_policy["state_file"] == ".cache/mcp/ko-stdict-mcp/data/state.json"
    assert prebuilt_policy["rejected_partial_indicators"] == [
        ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next",
        ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next-wal",
        ".cache/mcp/ko-stdict-mcp/data/db/stdict.sqlite.next-shm",
    ]
    assert prebuilt_policy["required_dictionary_status"] == {
        "ready": True,
        "schema_version": 2,
        "minimum_entry_count": 1,
    }
    assert prebuilt_policy["acceptance_checks"] == [
        "runtime_cache_readiness_status_ready",
        "ready_database_present",
        "ready_database_has_current_schema",
        "state_schema_version_current",
        "no_staging_or_wal_partial_indicators",
        "ready_database_metadata_present",
        "ready_database_entry_count_positive",
        "dictionary_status_ready_true",
        "dictionary_status_schema_version_current",
        "state_download_matches_ready_database_metadata",
        "cache_size_within_policy",
        "provenance_recorded_from_official_dictionary_dump",
        "partial_cache_removed_before_publish",
    ]
    assert prebuilt_policy["next_probe_allowed_when"] == "runtime_cache_readiness_status_ready"
    assert source.config["real_transport_preflight_required_checks"] == [
        "launch_exact_configured_command",
        "enforce_allowed_write_roots",
        "enforce_max_bootstrap_seconds",
        "enforce_max_cache_bytes",
        "enforce_runtime_cache_env_under_allowed_write_roots",
        "enforce_dictionary_data_dir_env_under_allowed_write_roots",
        "call_dictionary_status_only",
        "verify_no_refresh_dictionary_call",
        "verify_no_error_payload",
        "verify_cache_paths_under_allowed_root",
        "verify_cache_size_after_probe",
        "verify_prebuilt_cache_ready_before_probe",
        "verify_no_partial_cache_indicators",
        "verify_dictionary_status_ready_and_schema_current",
        "verify_prebuilt_cache_provenance",
        "record_probe_artifact_before_enablement",
    ]
    assert "cache_size_limit_exceeded" in source.config["real_transport_preflight_rollback_criteria"]
    assert "runtime_cache_env_outside_allowed_root" in source.config[
        "real_transport_preflight_rollback_criteria"
    ]
    assert "wrong_entrypoint_no_stdio_response" in source.config[
        "real_transport_preflight_rollback_criteria"
    ]
    assert "partial_cache_not_ready" in source.config[
        "real_transport_preflight_rollback_criteria"
    ]
    assert "prebuilt_cache_missing" in source.config["real_transport_preflight_rollback_criteria"]
    assert "prebuilt_cache_schema_mismatch" in source.config[
        "real_transport_preflight_rollback_criteria"
    ]
    assert "prebuilt_cache_partial_indicators_present" in source.config[
        "real_transport_preflight_rollback_criteria"
    ]
    assert source.config["fake_transport_smoke_test_status"] == "passed"
    assert (
        source.config["fake_transport_smoke_test_artifact"]
        == "_workspace/2026-04-29_cycle49_kostdict_fake_stdio_probe.json"
    )
    assert source.config["fake_transport_fixture"] == "fixtures/mcp/fake_ko_stdict_mcp.py"
    assert "runtime_data_bootstrap_review_required" not in source.config["activation_gates"]
    assert "bounded_real_transport_preflight_required" not in source.config["activation_gates"]
    assert "bootstrap_performance_review_required" not in source.config["activation_gates"]
    assert "prebuilt_cache_readiness_required" not in source.config["activation_gates"]
    assert "fake_transport_smoke_test_required" not in source.config["activation_gates"]
    assert "real_transport_smoke_test_required" not in source.config["activation_gates"]
    assert "production_monitoring_required" not in source.config["activation_gates"]
    assert "command_or_endpoint_unresolved" not in source.config["activation_gates"]
    assert "tool_resource_allowlist_required" not in source.config["activation_gates"]
    assert source.config["activation_gates"] == []


def test_kordoc_candidate_has_controlled_rollout_guard_metadata() -> None:
    category = load_category_config(_category_name())
    source = _mcp_source(category, "chrisryugj/kordoc")

    assert source.enabled is True
    assert source.config["activation_status"] == "real_transport_smoke_test_passed"
    assert source.config["metadata_checked_at"] == "2026-05-07T05:20:56+00:00"
    assert source.config["metadata_refresh_status"] == "passed"
    assert (
        source.config["metadata_refresh_artifact"]
        == "_workspace/2026-05-07_mcp_github_repository_metadata_refresh.json"
    )
    assert source.config["metadata_refresh_source"] == "github_rest_api"
    assert source.config["github_pushed_at"] == "2026-04-29T12:52:05Z"
    assert source.config["github_stars"] == 894
    assert source.config["github_head_sha"] == "13758461c931f1c00e24f9956dec51cec79594e0"
    assert source.config["production_enablement_status"] == "controlled_rollout_enabled"
    assert source.config["production_enablement_decision_status"] == "legacy_enabled_source_guard_applied"
    assert source.config["production_enablement_source_enabled_after_decision"] is True
    assert source.config["production_enablement_decision_failed_checks"] == []
    assert source.config["production_rollout_status"] == "active"
    assert source.config["production_rollout_enabled_at"] == "2026-04-14T04:35:00+00:00"
    assert source.config["production_rollout_guarded_at"] == "2026-04-29T11:14:18+00:00"
    assert source.config["production_rollout_monitored_at"] == "2026-05-08T07:10:42+00:00"
    assert (
        source.config["production_rollout_monitor_artifact"]
        == "_workspace/2026-05-08_kostdict_real_transport_enablement_smoke.json"
    )
    assert source.config["activation_gates"] == []
    assert source.config["production_monitoring_metrics"] == {
        "min_article_count": 1,
        "require_non_empty_summary_count_equals_article_count": True,
        "max_exact_fallback_link_count": 0,
        "max_duplicate_link_count": 0,
        "expected_source_name": "chrisryugj/kordoc",
        "expected_category": "korean_nlp_mcp",
    }
    assert "exact_fallback_link_count_above_zero" in source.config["production_rollback_criteria"]
    assert source.config["production_collection_cadence"] == "controlled_low_frequency_rollout"
    assert [tool["name"] for tool in source.config["tools"]] == ["detect_format"]
    assert source.config["tools"][0]["arguments"] == {
        "file_path": "fixtures/mcp/kordoc_smoke_sample.pdf"
    }


def test_mcp_category_quality_config_tracks_mcp_event_models() -> None:
    quality_config = load_category_quality_config(_category_name())
    data_quality = quality_config["data_quality"]
    assert isinstance(data_quality, dict)
    outputs = data_quality["quality_outputs"]
    assert isinstance(outputs, dict)
    assert outputs["tracked_event_models"] == [
        "mcp_directory_entry",
        "mcp_tool_result",
        "linked_repository_metadata",
        "risk_scope_signal",
    ]
