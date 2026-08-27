# Smart Data Extraction System

An intelligent, multi-stage data extraction pipeline that crawls university websites, collects evidence from programme pages and PDFs, extracts structured facts using LLMs, semantically normalizes the data, and outputs clean, categorized JSON files.

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup](#setup)
- [How to Run](#how-to-run)
- [CLI Reference](#cli-reference)
- [Output Structure](#output-structure)
- [Resuming Extraction](#resuming-extraction)
- [Currently Extracted Universities](#currently-extracted-universities)
- [Testing](#testing)

---

## Architecture

The pipeline processes each university through **8 sequential stages**:

```
┌──────────────────────────────────────────────────────────────────┐
│                    University Pipeline                           │
│                                                                  │
│  Stage 1: Programme Discovery                                   │
│    └─ Crawl sitemaps + BFS to find all programme pages           │
│                                                                  │
│  Stage 2: University-Level Data (QS Profile)                     │
│    └─ Extract rankings, stats from QS TopUniversities            │
│                                                                  │
│  Stage 3: Evidence Collection                                    │
│    └─ Download programme page + all linked child pages & PDFs    │
│                                                                  │
│  Stage 4: Evidence Pack Building                                 │
│    └─ Chunk and organize evidence into processable packs         │
│                                                                  │
│  Stage 5: Fact Extraction                                        │
│    └─ LLM (GPT-4o-mini) extracts raw facts from each chunk      │
│                                                                  │
│  Stage 6: Semantic Normalization                                 │
│    └─ LLM standardizes facts into consistent schema              │
│                                                                  │
│  Stage 7: Targeted Search Fallback                               │
│    └─ DuckDuckGo search for missing critical fields              │
│                                                                  │
│  Stage 8: Final Output                                           │
│    └─ Assemble normalized facts into category JSON files         │
└──────────────────────────────────────────────────────────────────┘
```

For a deep dive into the architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Project Structure

```
Extraction/
├── run_pipeline.py              # CLI entry point
├── main.py                      # Legacy standalone entry point
├── config.py                    # Configuration
├── schema.sql                   # Database schema for fact storage
│
├── pipelines/                   # Pipeline orchestration
│   ├── university_pipeline.py   # Main 8-stage pipeline
│   ├── pipeline_context.py      # Shared context object
│   ├── program_metadata.py      # Programme metadata model
│   └── run_context.py           # Run-level context
│
├── discovery/                   # Stage 1: Programme discovery
│   ├── engine.py                # Discovery orchestrator
│   ├── evaluation.py            # URL relevance evaluation
│   ├── scoring.py               # Programme URL scoring
│   ├── targeted_search.py       # Targeted web search fallback
│   ├── url_utils.py             # URL parsing utilities
│   └── strategies/              # Crawl strategies (sitemap, catalog, BFS)
│       ├── sitemap.py
│       ├── catalog.py
│       └── crawler.py
│
├── extractor/                   # Evidence collection
│   ├── extractor.py             # Web page extractor
│   └── link_discovery.py        # Child page link finder
│
├── knowledge/                   # Core extraction logic
│   ├── facts.py                 # Fact and FactCollection models
│   ├── models.py                # ProgramEvidence, EvidenceChunk
│   ├── prompts.py               # All LLM prompt templates
│   ├── evidence_pack_builder.py # Stage 4: Evidence pack assembly
│   │
│   ├── extractors/              # Stage 5: LLM fact extraction
│   │   └── program_extractor.py
│   │
│   ├── normalization/           # Stage 6: Semantic normalization
│   │   └── semantic_normalizer.py
│   │
│   ├── chunking/                # Text chunking utilities
│   │
│   ├── output/                  # Stage 8: Final output assembly
│   │   └── final_output_builder.py
│   │
│   ├── pdf/                     # PDF extraction & processing
│   │   ├── pdf_fact_extractor.py
│   │   └── document_classifier.py
│   │
│   ├── qs/                      # QS TopUniversities extraction
│   │   ├── qs_pipeline.py
│   │   ├── qs_profile_extractor.py
│   │   └── qs_ranking_extractor.py
│   │
│   ├── llm/                     # LLM providers & caching
│   │   ├── client.py            # Unified LLM client
│   │   ├── llm_cache.py         # Disk-based response cache
│   │   ├── openai_provider.py   # OpenAI (GPT-4o-mini)
│   │   ├── groq_provider.py     # Groq (fast inference)
│   │   └── nvidia_provider.py   # NVIDIA fallback
│   │
│   ├── billing/                 # Token usage tracking
│   │   ├── usage_tracker.py
│   │   ├── usage_record.py
│   │   └── pricing.py
│   │
│   ├── storage/                 # Fact persistence
│   │   └── fact_repository.py
│   │
│   └── enrichment/              # Data enrichment utilities
│
├── utils/                       # Shared utilities
│
├── data/                        # Output directory (auto-created)
│   ├── .cache/llm/              # LLM response cache (15,000+ entries)
│   ├── united_states/asu/       # Arizona State University data
│   ├── germany/uni_frankfurt/   # Goethe University Frankfurt data
│   └── ireland/ul/              # University of Limerick data
│
├── .env                         # API keys (not committed)
├── requirements.txt             # Python dependencies
└── ARCHITECTURE.md              # Detailed architecture documentation
```

---

## Setup

### Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Extraction
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Keys

Create a `.env` file in the project root with the following keys:

```env
# Required — Primary LLM provider
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini

# Optional — Groq (fast inference, used for normalization)
GROQ_API_KEY=gsk_your-key-here
GROQ_MODEL=openai/gpt-oss-120b

# Optional — NVIDIA fallback
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=openai/gpt-oss-120b

# Optional — Azure Document Intelligence (for scanned PDF extraction)
AZURE_IMG_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com
AZURE_PDF_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com
AZURE_IMG_KEY=your-key-here
AZURE_PDF_KEY=your-key-here
```

> **Note:** The pipeline currently uses **OpenAI GPT-4o-mini** as the primary LLM for both extraction and normalization. Groq and NVIDIA are available as fallback providers.

---

## How to Run

The pipeline is controlled by a single CLI entry point: `run_pipeline.py`.

### Quick Start — Extract One Programme (Test)

```bash
python run_pipeline.py --university "https://www.asu.edu" --programs 1
```

### Full University Extraction

```bash
python run_pipeline.py --university "https://www.asu.edu" --continue-on-error
```

### Full Extraction with QS Data

```bash
python run_pipeline.py \
  --university "https://www.asu.edu" \
  --qs-url "https://www.topuniversities.com/universities/arizona-state-university" \
  --continue-on-error
```

### Run in Background (Recommended for large universities)

```bash
# Windows PowerShell
Start-Process -NoNewWindow python -ArgumentList "-u", "run_pipeline.py", "--university", "https://www.asu.edu", "--qs-url", "https://www.topuniversities.com/universities/arizona-state-university", "--continue-on-error"

# Linux / macOS
nohup python -u run_pipeline.py \
  --university "https://www.asu.edu" \
  --qs-url "https://www.topuniversities.com/universities/arizona-state-university" \
  --continue-on-error > extraction.log 2>&1 &
```

---

## CLI Reference

```
python run_pipeline.py [OPTIONS]
```

| Flag | Required | Default | Description |
|---|---|---|---|
| `--university` | ✅ | — | Base URL of the university website |
| `--qs-url` | ❌ | `None` | QS TopUniversities profile URL for university-level data |
| `--programs` | ❌ | `None` (all) | Limit extraction to first N programmes (for testing) |
| `--country` | ❌ | Auto-detected | Country name for workspace folder structure |
| `--workspace` | ❌ | `data` | Root directory for all output data |
| `--continue-on-error` | ❌ | `False` | Skip failed programmes instead of stopping |
| `--verbose` | ❌ | `False` | Print extra debug information |

### Examples

```bash
# Test with 1 programme
python run_pipeline.py --university "https://www.ul.ie" --programs 1

# Extract 10 programmes from a German university
python run_pipeline.py --university "https://www.uni-frankfurt.de/en" --programs 10

# Full extraction with resilience
python run_pipeline.py --university "https://www.ul.ie" \
  --qs-url "https://www.topuniversities.com/universities/university-limerick" \
  --continue-on-error
```

---

## Output Structure

Each university gets its own directory tree under `data/`:

```
data/
├── .cache/
│   └── llm/                           # Disk-based LLM response cache
│       ├── <sha256-hash>.json         # Cached LLM responses (avoids re-extraction)
│       └── ...
│
└── <country>/
    └── <university-short-name>/
        ├── discovery.json              # All discovered programme URLs
        ├── qs_data/                    # QS TopUniversities data (if --qs-url provided)
        │   ├── qs_profile.json
        │   └── qs_rankings.json
        │
        └── programs/
            ├── 0001/
            │   ├── webpage/            # Raw HTML + converted Markdown
            │   ├── evidence/           # Child pages, link manifests
            │   ├── pdfs/              # Downloaded PDFs
            │   ├── facts/             # Raw + normalized LLM extractions
            │   └── final/             # ✅ Consumer-ready categorized JSON
            │       ├── admission_data.json
            │       ├── career_data.json
            │       ├── contacts_data.json
            │       ├── curriculum_data.json
            │       ├── documents_data.json
            │       ├── fees_data.json
            │       ├── housing_data.json
            │       ├── other_data.json
            │       ├── program_data.json
            │       ├── research_data.json
            │       ├── scholarships_data.json
            │       ├── statistics_data.json
            │       ├── student_life_data.json
            │       ├── visa_data.json
            │       └── build_summary.json
            ├── 0002/
            │   └── ...
            └── ...
```

### Output Categories

Each programme's `final/` directory contains JSON files organized by category:

| File | Description |
|---|---|
| `program_data.json` | Programme name, degree type, duration, language, overview |
| `admission_data.json` | Entry requirements, deadlines, GPA, test scores |
| `curriculum_data.json` | Course modules, credit hours, electives, specializations |
| `fees_data.json` | Tuition fees, cost breakdowns, payment schedules |
| `scholarships_data.json` | Available scholarships, eligibility, amounts |
| `career_data.json` | Career paths, employer info, salary data, outcomes |
| `student_life_data.json` | Campus life, clubs, extracurriculars |
| `contacts_data.json` | Department contacts, advisors, emails |
| `visa_data.json` | International student visa requirements |
| `housing_data.json` | On-campus housing, accommodation info |
| `documents_data.json` | Required application documents |
| `statistics_data.json` | Rankings, acceptance rates, enrollment numbers |
| `research_data.json` | Research areas, labs, publications |
| `other_data.json` | Uncategorized facts |
| `build_summary.json` | Extraction metadata (timestamp, fact count, sources) |

---

## Resuming Extraction

The pipeline supports **automatic checkpointing**. If an extraction is interrupted (crash, laptop shutdown, Ctrl+C), simply re-run the same command:

```bash
python run_pipeline.py --university "https://www.asu.edu" --continue-on-error
```

**How it works:**
- The pipeline checks for existing `final/` directories in each programme folder
- Programmes that already have completed output are **automatically skipped**
- Discovery results are cached in `discovery.json` and reused
- LLM responses are cached in `data/.cache/llm/` to avoid redundant API calls
- This means you can safely stop and restart the pipeline at any time

---

## Currently Extracted Universities

| University | Country | Programmes Extracted | Total Facts | Command |
|---|---|---|---|---|
| Arizona State University | United States | 206 | 19,908 | `python run_pipeline.py --university "https://www.asu.edu" --qs-url "https://www.topuniversities.com/universities/arizona-state-university" --continue-on-error` |
| Goethe University Frankfurt | Germany | 99 | 612 | `python run_pipeline.py --university "https://www.uni-frankfurt.de/en" --qs-url "https://www.topuniversities.com/universities/goethe-university-frankfurt" --continue-on-error` |
| University of Limerick | Ireland | 304 | 18,263 | `python run_pipeline.py --university "https://www.ul.ie" --qs-url "https://www.topuniversities.com/universities/university-limerick" --continue-on-error` |

> **Cost estimate:** ~$0.04 per programme using OpenAI GPT-4o-mini (~$23-25 total for all 609 programmes).

---

## Testing

The project includes test scripts for individual pipeline components:

```bash
# Test fact extraction from a programme page
python test_program_extractor.py

# Test semantic normalization
python test_semantic_normalizer.py

# Test final output assembly
python test_final_output_builder.py

# Test QS profile extraction
python test_qs_profile_extractor.py

# Test QS ranking extraction
python test_qs_ranking_extractor.py

# Test QS output builder
python test_qs_output_builder.py

# Test PDF fact extraction
python test_pdf_fact_extractor.py
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | OpenAI API key (GPT-4o-mini) |
| `OPENAI_MODEL` | ❌ | Model name override (default: `gpt-4o-mini`) |
| `GROQ_API_KEY` | ❌ | Groq API key (fallback provider) |
| `GROQ_MODEL` | ❌ | Groq model name |
| `NVIDIA_API_KEY` | ❌ | NVIDIA API key (fallback provider) |
| `NVIDIA_MODEL` | ❌ | NVIDIA model name |
| `AZURE_IMG_ENDPOINT` | ❌ | Azure Document Intelligence endpoint (image OCR) |
| `AZURE_PDF_ENDPOINT` | ❌ | Azure Document Intelligence endpoint (PDF OCR) |
| `AZURE_IMG_KEY` | ❌ | Azure image API key |
| `AZURE_PDF_KEY` | ❌ | Azure PDF API key |

---

## License

Internal use only.
