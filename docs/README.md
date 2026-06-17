# Taghag Documentation Index

Welcome to the Taghag documentation repository. The documentation has been sorted into four functional domains to help you find what you're looking for quickly.

## 📂 `architecture/`
Contains high-level system design, database schemas, and integration specifications.
- `additional_sources.md` - Research notes on handling additional audio sources in Roon.
- `apple_music_understanding_integration.md` - Technical reference and integration design for the Apple Music Understanding Framework.
- `autonomous_intelligence_engine_design.md` - Design spec for exporting the intelligence engine from Taghag to Tagslut.
- `canonical_metadata_schemas.md` - Core metadata schema definitions for tracks and assets.
- `direct_leveldb_access.md` - Technical notes on directly accessing Roon's underlying LevelDB.
- `dsp_metadata_integration.md` - Specifications for integrating multi-platform DSP metadata.
- `file_changes_and_library_rescan.md` - Notes on how Roon handles file modifications and library rescanning.
- `cuecifer_overlay_design.md` - Technical design for delivering Cuecifer as an overlay to Taghag.
- `manifest_stage_design.md` - Design document for the manifest compilation stage.
- `roon_extension_architecture.md` - Architectural overview of the Headless Roon Extension pivot.
- `roon_extension_ui_actions.md` - UI & Actions spec for the Roon Extension.
- `roon_metadata_policy.md` - Rules and policies for writing metadata recognized by Roon.
- `supabase_database_schema.md` - Comprehensive documentation of the Supabase database schema.
- `taghag_stage_pipeline_design.md` - Design documentation for the primary tagging pipeline.

## 📂 `reports/`
Contains deep-dive technical reports, intelligence engine whitepapers, and phase summaries.
- `autonomous_intelligence_engine_whitepaper.md` - The complete technical whitepaper and datasheet for the Cuecifer intelligence engine.
- `cuecifer_a_z_technical_report.md` - Comprehensive A-Z technical summary of the Cuecifer engine.
- `cuecifer_phase_2_report.md` - Summary of accomplishments from Phase 2 of the Cuecifer sprint.
- `taghag_intelligence_engine_deep_dive.md` - Specific deep-dive covering the Supabase vectors and cue pathfinder.
- `tier_review.md` - Manual tier review and dataset validation summary.

## 📂 `management/`
Contains project planning and historical milestone briefs.
- `manifest_stage_plan.md` - Implementation plan for the manifest stage.
- `project_brief.md` - The original Gemini Project Brief.
- `taghag_stage_pipeline_plan.md` - Implementation plan for the stage pipeline.

## 📂 `archive/`
Contains historically obsolete execution plans and legacy MP3/Rekordbox-era designs. Agents should ignore these unless instructed otherwise.

## 📂 `guides/`
Contains troubleshooting, operational references, and issue resolution guides.
- `migration_reference.md` - Guidelines and SQL references for executing Supabase migrations.
- `roon_identification_failure_fix.md` - RCA and fix guide for the Roon "Paper Cuts #1" identification failure.
