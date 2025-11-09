---
title: Vetrix Podcast
title_long: AI-powered medical literature extraction pipeline
finished: false
type: normal
picture: projects/vetrix-podcast.png
template: project-single
groups: anes
default_group: anes
people: Rob Tolboom
description: Intelligent medical literature extraction pipeline using LLM vision capabilities to transform research PDFs into structured data with automatic critical appraisal and podcast episodes.
bibkeys:
category: projects
---

## Clinical Problem / Problem description

Medical professionals and researchers need to quickly assess and synthesize evidence from numerous medical research papers. Manual extraction of structured data from PDFs is time-consuming, error-prone, and particularly challenging when dealing with complex tables, figures, and varied publication types. Additionally, systematic critical appraisal using tools like RoB 2, ROBINS-I, GRADE, and PROBAST requires significant expertise and manual effort, leading to inconsistent assessments and delayed evidence-based decision making.

## Solution / Project summary

Vetrix Podcast is an intelligent data extraction pipeline that processes medical literature PDFs through a five-stage workflow:

1. **Classification** - Automatically identifies publication type (interventional trials, observational studies, systematic reviews, prediction models, editorials)
2. **Extraction** - Uses LLM vision models to extract complete structured data while preserving tables, figures, and complex formatting
3. **Validation & Correction** - Iteratively validates and corrects extracted data through dual-tier schema and LLM validation
4. **Critical Appraisal** (in development) - Automatically performs risk of bias assessment, GRADE ratings, and quality evaluation using study-type-specific tools
5. **Podcast creation** (in development) - Generation of podcast transcript and text-to speech podcast generation.

The pipeline provides both a web interface (Streamlit) and command-line interface for flexible integration into research workflows.

## Background

Evidence-based medicine relies on rigorous assessment of medical literature quality and applicability. Traditional approaches using text extraction from PDFs lose critical information in tables and figures. Manual critical appraisal is subjective, time-consuming, and inconsistently applied. Recent advances in multimodal LLMs enable direct PDF-to-structured-data conversion with vision capabilities that preserve complete document fidelity.

## Aim / Task

- Develop a production-ready pipeline for automated medical literature extraction and appraisal
- Support all major publication types with type-specific extraction schemas
- Implement iterative validation and correction to ensure data quality (≥90% completeness, ≥95% accuracy)
- Integrate critical appraisal tools (RoB 2, ROBINS-I, PROBAST, AMSTAR 2, GRADE) for automated quality assessment
- Provide structured JSON outputs suitable for downstream analysis, reports, and podcast script generation
- Enable rapid evidence synthesis for clinical decision-making and multidisciplinary team meetings

## Data

The pipeline processes medical research PDFs (≤100 pages, ≤32 MB) from various sources:
- Randomized controlled trials (RCTs)
- Observational studies (cohort, case-control, cross-sectional)
- Systematic reviews and meta-analyses
- Prediction and prognostic model studies
- Diagnostic accuracy studies
- Editorials and opinion pieces

Outputs are validated against publication-type-specific JSON schemas covering metadata, study design, population, interventions, outcomes, results, and critical appraisal metrics.

## Approach

**Technical Architecture:**

- **Vision-first extraction**: Direct PDF-to-LLM processing preserves tables, figures, and layout
- **Schema-driven validation**: JSON Schema enforcement with dual-tier validation (local + LLM)
- **Iterative quality improvement**: Automatic correction loops until quality thresholds are met
- **Provider abstraction**: Support for OpenAI (GPT-5) and Anthropic (Claude) models
- **Modular prompts**: Study-type-specific prompts for classification, extraction, validation, correction, and appraisal

**Quality Assurance:**

- Configurable quality thresholds (completeness, accuracy, schema compliance)
- Early stopping when quality degrades
- Best-iteration selection based on composite quality scores
- Comprehensive logging and iteration history tracking

## Goals

- Implement core extraction pipeline with classification, extraction, and validation (complete)
- Achieve dual-tier validation with iterative correction (complete)
- Add critical appraisal module with tool-specific assessments (in progress)
- Integrate GRADE certainty ratings and applicability assessment (in progress)
- Develop automated report generation from structured outputs (planned)
- Create podcast script generation with quality context (planned)
- Deploy as self-hosted service for UMCG researchers (planned)

## Funding

None