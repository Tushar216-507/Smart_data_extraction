# Smart Data Extraction System

## Architecture, Components, Data Flow, and Final Output

**Current status:** Programme extraction, semantic normalization,
programme final-output generation, QS profile extraction, QS ranking
extraction, and QS final-output generation are operational.

**Primary goal:**

> One university name in → one complete, organized university dataset
> out.

------------------------------------------------------------------------

# 1. System Overview

The Smart Data Extraction System is a modular university intelligence
pipeline. It collects information from university websites and external
sources, preserves raw evidence, extracts structured facts, normalizes
those facts, and produces validated JSON outputs.

The planned end-to-end flow is:

``` text
University name
      ↓
run_pipeline.py
      ↓
University workspace creation
      ↓
University website and programme discovery
      ↓
Evidence collection
      ↓
Programme fact extraction
      ↓
Semantic normalization
      ↓
Programme final outputs
      ↓
QS profile and ranking extraction
      ↓
Optional PDF extraction
      ↓
University-level aggregation
      ↓
Complete validated university dataset
```

The architecture is modular so that every phase can be tested, rerun,
replaced, or resumed independently.

------------------------------------------------------------------------

# 2. Architectural Principles

## 2.1 Single responsibility

Each component performs one primary task:

-   Crawlers collect pages.
-   Evidence builders prepare source material.
-   Chunkers divide large inputs.
-   Extractors identify facts.
-   Normalizers standardize meaning.
-   Output builders organize data.
-   Validators detect missing or dropped data.
-   `main.py` coordinates the pipeline.

## 2.2 Evidence-first processing

Raw HTML, source content, extracted facts, and normalized facts are
preserved before final JSON is generated.

Benefits:

-   Failed phases can be resumed.
-   Expensive LLM calls do not need to be repeated unnecessarily.
-   Incorrect facts can be traced to their evidence.
-   Prompts can be retested against existing data.
-   Extraction quality can be audited.

## 2.3 High recall before normalization

The programme extractor prioritizes maximum information capture. A
stricter prompt previously reduced extraction from about 33 facts to 17,
so the broader high-recall prompt was restored.

The current strategy is:

``` text
Extract broadly
      ↓
Preserve all useful facts
      ↓
Normalize later
      ↓
Organize final output
```

## 2.4 No silent data loss

Output builders measure:

-   Input facts
-   Unique facts
-   Duplicates removed
-   Handled facts
-   Unhandled facts
-   Written facts
-   Dropped facts

The tested programme output preserved all 144 unique normalized facts.

------------------------------------------------------------------------

# 3. High-Level Architecture

``` text
                           UNIVERSITY NAME
                                  │
                                  ▼
                       ┌──────────────────┐
                       │ run_pipeline.py  │
                       │UniversityPipeline│
                       └────────┬─────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ University Site  │  │    QS Profile    │  │  PDF Documents   │
│ Crawl/Discovery  │  │    Extraction    │  │ Optional Phase   │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Programme Pages  │  │ Profile + Rank   │  │ PDF Evidence     │
│ and Evidence     │  │ Data             │  │ and Facts        │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         ▼                     ▼                     │
┌──────────────────┐  ┌──────────────────┐           │
│ EvidenceChunker  │  │ QSOutputBuilder  │           │
└────────┬─────────┘  └────────┬─────────┘           │
         ▼                     ▼                     │
┌──────────────────┐      qs_data.json               │
│ProgramExtractor  │                                  │
└────────┬─────────┘                                  │
         ▼                                            │
 raw_program_facts.json                               │
         │                                            │
         ▼                                            │
┌──────────────────┐                                  │
│SemanticNormalizer│                                  │
└────────┬─────────┘                                  │
         ▼                                            │
normalized_program_facts.json                         │
         │                                            │
         ▼                                            │
┌──────────────────┐                                  │
│FinalOutputBuilder│                                  │
└────────┬─────────┘                                  │
         ▼                                            │
Programme final JSON files                            │
         │                                            │
         └──────────────────┬─────────────────────────┘
                            ▼
                  University Aggregator
                            │
                            ▼
                COMPLETE UNIVERSITY DATA
```

------------------------------------------------------------------------

# 4. Current Logical Project Structure

``` text
Extraction/
│
├── run_pipeline.py
├── main.py
├── config.py
├── prompts.py
│
├── pipelines/
│   ├── program_metadata.py
│   ├── pipeline_context.py
│   └── university_pipeline.py
│
├── knowledge/
│   ├── facts.py
│   ├── evidence_pack_builder.py
│   │
│   ├── chunking/
│   │   └── evidence_chunker.py
│   │
│   ├── extractors/
│   │   └── program_extractor.py
│   │
│   ├── normalization/
│   │   └── semantic_normalizer.py
│   │
│   ├── output/
│   │   └── final_output_builder.py
│   │
│   ├── llm/
│   │   ├── client.py
│   │   ├── openai_provider.py
│   │   ├── groq_provider.py
│   │   └── nvidia_provider.py
│   │
│   └── qs/
│       ├── qs_profile_extractor.py
│       ├── qs_ranking_extractor.py
│       └── qs_output_builder.py
│
├── data/
│   ├── 0001/
│   │   └── knowledge/
│   │       ├── raw_program_facts.json
│   │       └── normalized_program_facts.json
│   │
│   └── qs/
│       └── <university-slug>/
│           ├── raw/
│           ├── extracted/
│           └── final/
│
├── test_program_extractor.py
├── test_semantic_normalizer.py
├── test_final_output_builder.py
├── test_qs_profile_extractor.py
├── test_qs_ranking_extractor.py
└── test_qs_output_builder.py
```

------------------------------------------------------------------------

# 5. Core Fact Model

## `knowledge/facts.py`

This module defines the shared knowledge representation.

### `SourceReference`

``` python
@dataclass
class SourceReference:
    source_type: str
    source_id: str
    title: str
    url: str = ""
```

  Field           Meaning
  --------------- -------------------------------------------------
  `source_type`   Programme, webpage, PDF, or another source type
  `source_id`     Internal source identifier
  `title`         Human-readable source title
  `url`           Original URL when available

### `ExtractedFact`

``` python
@dataclass
class ExtractedFact:
    category: str
    field: str
    value: Any
    confidence: float = 1.0
    source: SourceReference = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

Example:

``` json
{
  "category": "admission",
  "field": "language_requirement",
  "value": "German language proficiency is required",
  "confidence": 1.0
}
```

The source is optional so extraction does not fail when a source
reference has not yet been attached. Source enrichment can be added
later.

### `FactCollection`

Stores multiple facts and provides:

-   `add(fact)`
-   `by_category(category)`
-   `by_field(field)`

------------------------------------------------------------------------

# 6. Evidence Layer

## `EvidencePackBuilder`

The evidence-pack builder loads collected programme information and
creates a stable input for knowledge extraction.

``` text
Raw programme files
        ↓
EvidencePackBuilder
        ↓
Programme evidence pack
```

This separates crawling from extraction. The extractor does not need to
know how the source page was downloaded or converted.

## `EvidenceChunker`

Large evidence may exceed model limits. The chunker divides it into
manageable pieces while preserving context.

Responsibilities:

-   Split large evidence
-   Avoid oversized LLM requests
-   Preserve useful context
-   Assign stable chunk IDs
-   Allow independent chunk processing

Example:

``` text
Programme evidence
├── evidence_0001
├── evidence_0002
├── evidence_0003
└── evidence_0004
```

------------------------------------------------------------------------

# 7. LLM Layer

## `LLMClient`

`LLMClient` provides one interface for all model providers.

``` text
Extractor/Normalizer
        ↓
     LLMClient
        ↓
 ┌──────┼──────┐
 ↓      ↓      ↓
OpenAI Groq  NVIDIA
```

Benefits:

-   Extractors do not depend on one vendor.
-   Providers can be replaced without rewriting business logic.
-   Fallback behavior can be centralized.
-   Configuration remains separate from extraction.

## `OpenAIProvider`

Used for high-quality structured extraction and translation when
required.

## `GroqProvider`

Uses Groq's native Python library. The project currently uses models
such as:

``` text
openai/gpt-oss-120b
```

Groq is fast, but large normalization requests can exceed
token-per-minute limits.

## NVIDIA fallback

NVIDIA uses an OpenAI-compatible endpoint:

``` python
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)
```

The intended fallback flow is:

``` text
Groq request
    ├── Success → return result
    └── Quota/rate-limit failure
                    ↓
                 NVIDIA
```

------------------------------------------------------------------------

# 8. Prompt Layer

## `prompts.py`

This module contains the extraction and normalization instructions.

The programme extraction prompt is intentionally comprehensive and
covers:

-   Programme identity
-   Degree information
-   Duration
-   Study mode
-   Language
-   Admissions
-   Applications
-   Deadlines
-   Curriculum
-   Modules
-   Credits
-   Fees
-   Careers
-   Research
-   Contacts
-   Student support
-   International information

The extraction prompt focuses on recall. Semantic cleanup happens later.

------------------------------------------------------------------------

# 9. Programme Extraction

## `ProgramExtractor`

The programme extractor converts evidence into structured facts.

``` text
Programme evidence
        ↓
EvidenceChunker
        ↓
Chunk 1 → LLM → facts
Chunk 2 → LLM → facts
Chunk 3 → LLM → facts
        ↓
Combined FactCollection
        ↓
raw_program_facts.json
```

Responsibilities:

-   Accept programme evidence
-   Generate chunks
-   Process chunks independently
-   Parse LLM JSON
-   Create `ExtractedFact` objects
-   Combine all facts

Raw facts intentionally preserve detailed and potentially overlapping
information.

Example output:

``` text
data/0001/knowledge/raw_program_facts.json
```

------------------------------------------------------------------------

# 10. Semantic Normalization

## `SemanticNormalizer`

The semantic normalizer converts raw facts into a consistent vocabulary
and structure.

Responsibilities:

-   Standardize categories
-   Standardize field names
-   Preserve detailed values
-   Reduce semantic inconsistency
-   Keep distinct information
-   Process grouped normalization chunks

Current normalization groups include:

-   Identity and overview
-   Admission and language
-   Career and research
-   Fees and student support
-   Institution and contacts
-   Curriculum

Test result:

``` text
143 raw facts
10 normalization chunks
144 normalized facts
```

Output:

``` text
data/0001/knowledge/normalized_program_facts.json
```

Normalization is separate because combining strict normalization with
extraction reduced recall.

------------------------------------------------------------------------

# 11. Programme Final Output

## `FinalOutputBuilder`

This builder converts normalized facts into consumer-facing JSON files.

Current sections:

  Section          Contents
  ---------------- --------------------------------------------
  `program`        Name, degree, duration, language, overview
  `admission`      Requirements, applications, deadlines
  `curriculum`     Modules, credits, structure
  `career`         Career paths and outcomes
  `fees`           Tuition and related costs
  `contacts`       Programme and institution contacts
  `student_life`   Student support and related information

Current validation result:

``` text
Input facts:               144
Unique facts:              144
Handled facts:             144
Unhandled facts:             0
Written facts:             144
Dropped facts:               0
```

------------------------------------------------------------------------

# 12. QS Pipeline

QS provides university-level information that complements the university
website programme pipeline.

Extracted areas include:

-   University identity
-   QS identifiers
-   Campus information
-   Student statistics
-   Faculty statistics
-   International statistics
-   Cost of living
-   Rankings
-   Ranking history
-   Ranking criteria
-   Social links
-   Images

Flow:

``` text
QS profile page
       ↓
QSProfileExtractor
       ↓
profile_data.json
       ↓
Discovered ranking endpoints
       ↓
QSRankingExtractor
       ↓
rankings_data.json
       ↓
QSOutputBuilder
       ↓
qs_data.json
```

------------------------------------------------------------------------

# 13. `QSProfileExtractor`

Responsibilities:

-   Download QS profile HTML
-   Reuse cached raw HTML when QS returns HTTP 403
-   Preserve raw HTML
-   Parse JSON-LD
-   Extract identifiers
-   Extract university identity
-   Extract campus/address information
-   Extract statistics
-   Extract cost-of-living data
-   Extract social links
-   Extract images
-   Discover ranking AJAX endpoints
-   Save structured profile JSON

Output:

``` text
data/qs/<university-slug>/
├── raw/
│   └── profile.html
└── extracted/
    └── profile_data.json
```

For LMU, it found:

-   University name
-   QS profile ID
-   Drupal node ID
-   Profile URL
-   University slug
-   Logo
-   Campus
-   Social links
-   Images
-   Statistics
-   Cost of living
-   Four ranking endpoints

------------------------------------------------------------------------

# 14. `QSRankingExtractor`

The ranking extractor reads endpoints discovered by the profile
extractor.

The Drupal AJAX responses contain:

-   Ranking chart history
-   Current rank
-   Ranking criteria
-   Criteria scores
-   Overall score

Responsibilities:

-   Load endpoints from `profile_data.json`
-   Download every endpoint
-   Preserve raw responses
-   Parse ranking history
-   Parse current rankings
-   Parse criteria and scores
-   Remove duplicate history entries
-   Save combined ranking JSON

Output:

``` text
data/qs/<university-slug>/
├── raw/
│   └── rankings/
│       ├── ranking_513.json
│       ├── ranking_516.json
│       ├── ranking_4085.json
│       └── ranking_4093.json
└── extracted/
    └── rankings_data.json
```

LMU result:

``` text
Ranking groups:           4
Ranking history records: 27
Ranking criteria:        40
Failed endpoints:         0
```

QS World University Rankings:

``` text
Current year:  2027
Current rank:  #61
Overall score: 79.6
```

------------------------------------------------------------------------

# 15. `QSOutputBuilder`

Combines:

``` text
profile_data.json
        +
rankings_data.json
        ↓
qs_data.json
```

Responsibilities:

-   Merge profile and ranking information
-   Preserve source metadata
-   Preserve identifiers
-   Organize locations
-   Organize statistics
-   Preserve cost-of-living data
-   Clean ranking history
-   Clean ranking criteria
-   Deduplicate records
-   Preserve social links and media
-   Add build metadata
-   Validate output

Output:

``` text
data/qs/<university-slug>/final/qs_data.json
```

Validated LMU result:

``` text
Rankings:               4
Ranking history:       27
Ranking criteria:      40
Campuses:               1
Social links:           3
University images:     14
Statistics sections:    4
Cost-of-living data:  Yes
```

------------------------------------------------------------------------

# 16. Test Suite

  -----------------------------------------------------------------------
  Test                                Purpose
  ----------------------------------- -----------------------------------
  `test_program_extractor.py`         Tests evidence-to-fact extraction

  `test_semantic_normalizer.py`       Tests normalization and chunking

  `test_final_output_builder.py`      Tests programme final outputs and
                                      fact preservation

  `test_qs_profile_extractor.py`      Tests QS profile extraction

  `test_qs_ranking_extractor.py`      Tests ranking history, criteria,
                                      and scores

  `test_qs_output_builder.py`         Tests final QS merge and
                                      preservation
  -----------------------------------------------------------------------

The tests print detailed extraction summaries because data quality must
be inspected, not only marked pass/fail.

------------------------------------------------------------------------

# 17. Current Data Flows

## Programme flow

``` text
Programme page
      ↓
Raw content
      ↓
EvidencePackBuilder
      ↓
EvidenceChunker
      ↓
ProgramExtractor
      ↓
raw_program_facts.json
      ↓
SemanticNormalizer
      ↓
normalized_program_facts.json
      ↓
FinalOutputBuilder
      ↓
program_data.json
admission_data.json
curriculum_data.json
career_data.json
fees_data.json
contacts_data.json
student_life_data.json
build_summary.json
```

## QS flow

``` text
QS profile URL
      ↓
QSProfileExtractor
      ├── raw/profile.html
      ├── profile_data.json
      └── ranking endpoints
                 ↓
        QSRankingExtractor
                 ├── raw ranking JSON
                 └── rankings_data.json
                              ↓
profile_data.json ────────────┤
                              ↓
                     QSOutputBuilder
                              ↓
                         qs_data.json
```

------------------------------------------------------------------------

# 18. Planned University Workspace

During testing, `data/0001` represents one programme. Production should
isolate every university.

``` text
data/
└── universities/
    └── ludwig-maximilian-university-of-munich/
        ├── metadata/
        │   └── university.json
        │
        ├── sources/
        │   ├── webpages/
        │   └── pdfs/
        │
        ├── programs/
        │   ├── 0001/
        │   │   ├── raw/
        │   │   ├── evidence/
        │   │   ├── knowledge/
        │   │   │   ├── raw_program_facts.json
        │   │   │   └── normalized_program_facts.json
        │   │   └── final/
        │   │       ├── program_data.json
        │   │       ├── admission_data.json
        │   │       ├── curriculum_data.json
        │   │       ├── career_data.json
        │   │       ├── fees_data.json
        │   │       ├── contacts_data.json
        │   │       ├── student_life_data.json
        │   │       └── build_summary.json
        │   ├── 0002/
        │   └── 0003/
        │
        ├── qs/
        │   ├── raw/
        │   ├── extracted/
        │   └── final/
        │       └── qs_data.json
        │
        ├── pdf/
        │   ├── raw/
        │   ├── extracted/
        │   └── final/
        │
        └── final/
            ├── university_data.json
            ├── programs_data.json
            ├── admissions_data.json
            ├── curriculum_data.json
            ├── rankings_data.json
            ├── fees_data.json
            ├── contacts_data.json
            ├── student_life_data.json
            ├── sources.json
            └── extraction_summary.json
```

------------------------------------------------------------------------

# 19. Planned Final Outputs

## `university_data.json`

University identity and university-level information.

``` json
{
  "university": {
    "name": "Ludwig-Maximilians-Universität München",
    "country": "Germany",
    "city": "Munich",
    "description": "...",
    "website": "...",
    "logo_url": "..."
  },
  "identifiers": {
    "qs_profile_id": 420,
    "drupal_node_id": 294840
  },
  "campuses": [],
  "statistics": {},
  "cost_of_living": {}
}
```

## `programs_data.json`

Summary of every programme.

``` json
{
  "university": "Ludwig-Maximilians-Universität München",
  "total_programs": 2,
  "programs": [
    {
      "program_id": "0001",
      "name": "Egyptology and Coptology",
      "degree": "...",
      "duration": "...",
      "language": "..."
    }
  ]
}
```

## `admissions_data.json`

``` json
{
  "programs": [
    {
      "program_id": "0001",
      "program_name": "Egyptology and Coptology",
      "requirements": [],
      "application_process": [],
      "deadlines": []
    }
  ]
}
```

## `curriculum_data.json`

``` json
{
  "programs": [
    {
      "program_id": "0001",
      "program_name": "Egyptology and Coptology",
      "curriculum": {
        "modules": [],
        "credits": [],
        "structure": []
      }
    }
  ]
}
```

## `rankings_data.json`

``` json
{
  "rankings": [
    {
      "ranking_id": 513,
      "name": "QS World University Rankings",
      "current": {
        "year": 2027,
        "rank": "#61",
        "score": 79.6
      },
      "history": [],
      "criteria": []
    }
  ]
}
```

## `extraction_summary.json`

``` json
{
  "status": "success",
  "programs_discovered": 2,
  "programs_processed": 2,
  "programs_failed": 0,
  "raw_facts": 300,
  "normalized_facts": 295,
  "facts_written": 295,
  "facts_dropped": 0,
  "qs_profile_extracted": true,
  "qs_rankings_extracted": 4,
  "pdf_extraction_enabled": false
}
```

------------------------------------------------------------------------

# 20. `run_pipeline.py` (CLI Orchestrator)

Target command:

``` bash
python run_pipeline.py --university "https://www.lmu.de/en/"
```

Options available:

``` bash
python run_pipeline.py --university "https://www.lmu.de/en/" --programs 5 --continue-on-error --workspace data
```

Conceptual orchestration (handled by `UniversityPipeline`):

``` python
def run(self, university_url, program_limit=None):
    
    # 1. Workspace initialization
    workspace = WorkspaceManager(...)

    # 2. Programme discovery
    programs = discover_programs(university_url)

    # 3. Per-programme execution
    for program in programs:
        collect_evidence(workspace, program)
        build_evidence_pack(workspace, program)
        extract_facts(workspace, program)
        normalize_facts(workspace, program)
        build_output(workspace, program)

    # Note: QS Extraction and PDF extraction can be integrated here
    # as independent stages.
```

`run_pipeline.py` only coordinates components through the `UniversityPipeline` class, avoiding extraction business logic.

------------------------------------------------------------------------

# 21. PDF Extraction Status

PDF extraction is postponed.

Reasons:

-   Azure OpenAI access is expected later.
-   Local OCR such as PaddleOCR may consume significant laptop
    resources.
-   Programme and QS pipelines can be completed independently.

Future options:

-   Azure Document Intelligence
-   Azure OpenAI-assisted extraction
-   Cloud OCR
-   Docling for text-based PDFs
-   Lightweight text extraction before OCR fallback

The PDF pipeline should reuse the common fact architecture:

``` text
PDF
 ↓
PDF extractor
 ↓
Evidence chunks
 ↓
ExtractedFact objects
 ↓
Semantic normalization
 ↓
Final university aggregation
```

------------------------------------------------------------------------

# 22. Current Completion Status

  Component                        Status
  -------------------------------- -------------
  Programme evidence foundation    Complete
  Evidence chunking                Complete
  Programme extraction             Complete
  High-recall prompt               Complete
  Fact models                      Complete
  Semantic normalization           Complete
  Normalization chunking           Complete
  Groq provider                    Complete
  NVIDIA fallback                  Implemented
  OpenAI provider                  Available
  Programme final-output builder   Complete
  Fact-preservation validation     Complete
  QS profile extraction            Complete
  QS raw HTML preservation         Complete
  QS cached-HTML fallback          Complete
  Ranking endpoint discovery       Complete
  Ranking history extraction       Complete
  Ranking criteria extraction      Complete
  Ranking score extraction         Complete
  QS final-output builder          Complete
  QS output validation             Complete
  PDF extraction                   Deferred
  University workspace builder     Complete
  University pipeline orchestrator Complete
  University-level aggregator      Pending
  Full integration                 Complete
  Three-university testing         Pending

------------------------------------------------------------------------

# 23. Known Cleanup Items

## QS ranking names

Some ranking IDs may still have generic names:

``` text
QS Ranking 4085
QS Ranking 4093
```

These should eventually be identified from page context or a verified
mapping.

## Generic scholarship content

Some scholarship content is general QS guidance rather than
university-specific information.

It should be labeled clearly:

``` json
{
  "source_type": "general_qs_resources",
  "university_scholarships_confirmed": false
}
```

## QS programme content

QS programme information is preserved as supplementary content but is
not the authoritative programme source. The university website
extraction pipeline is more detailed.

## Source references

The fact model supports optional source references. Full source
attachment can be added later.

``` json
{
  "field": "duration",
  "value": "4 semesters",
  "sources": [
    {
      "source_type": "program",
      "source_id": "0001",
      "title": "Programme page",
      "url": "..."
    }
  ]
}
```

------------------------------------------------------------------------

# 24. Recommended Next Steps

1.  Build `UniversityWorkspaceBuilder`.
2.  Move all outputs under a university-specific folder.
3.  Build the university-level aggregator.
4.  Connect programme processing to `main.py`.
5.  Connect QS processing to `main.py`.
6.  Add resumable phase execution.
7.  Add final validation.
8.  Run one complete university.
9.  Run three-university end-to-end testing.
10. Add PDF extraction when cloud extraction access is available.

The next priority is integration rather than adding more isolated
extractors.

------------------------------------------------------------------------

# 25. Final Goal

Input:

``` text
"Ludwig Maximilian University of Munich"
```

Output:

``` text
Complete university workspace
├── raw source evidence
├── programme evidence
├── raw extracted facts
├── normalized facts
├── programme-level final JSON
├── QS profile data
├── QS ranking data
├── optional PDF data
├── university-level aggregated JSON
├── source metadata
└── extraction and validation summary
```

The final system should be:

-   Structured
-   Reproducible
-   Source-aware
-   Modular
-   Provider-independent
-   Resume-friendly
-   Validated against data loss
-   Easy to consume through APIs, databases, search systems, and AI
    applications

------------------------------------------------------------------------

# 26. Summary

The project has evolved beyond a scraper into a multi-stage knowledge
extraction system:

``` text
Collect
   ↓
Preserve evidence
   ↓
Chunk
   ↓
Extract facts
   ↓
Normalize semantics
   ↓
Build structured outputs
   ↓
Merge QS data
   ↓
Validate preservation
   ↓
Aggregate complete university data
```

The programme pipeline and QS pipeline are independently operational.
The major remaining work is orchestration: university workspaces,
university-level aggregation, and complete `main.py` integration.
