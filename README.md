# Smart Data Extraction System

An intelligent, multi-stage data extraction pipeline for university websites. This system collects raw web data, extracts structured facts using LLMs, semantically normalizes the information, and organizes it into clean JSON output formats.

## Architecture

The project is built around an evidence-first, modular architecture. 

1. **Discovery**: Finds programme pages on a university website using sitemaps and BFS crawling.
2. **Evidence Collection**: Downloads pages and PDFs, and builds a comprehensive evidence pack.
3. **Fact Extraction**: Uses LLMs (Groq, OpenAI, or NVIDIA fallback) to extract raw facts from the evidence.
4. **Semantic Normalization**: Standardizes the extracted facts into a consistent schema.
5. **Output Generation**: Assembles the normalized facts into domain-specific JSON files (e.g., `admissions_data.json`, `curriculum_data.json`).
6. **QS Extraction**: Independent pipeline for extracting QS TopUniversities profile and ranking data.

For a deep dive into the architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Setup & Requirements

### 1. Install Dependencies

You will need Python 3.9+ and the required packages.

```bash
pip install requests beautifulsoup4 curl_cffi trafilatura groq openai
```
*(Check your specific environment for any additional dependencies required by the modules).*

### 2. API Keys

This project uses LLM providers for extraction and normalization. You must configure your API keys in a `.env` file or export them to your environment.

**Required:**
- `GROQ_API_KEY`: Primary LLM provider for fast extraction and normalization.

**Optional (Fallback):**
- `NVIDIA_API_KEY`: Fallback LLM provider in case Groq is rate-limited.
- `OPENAI_API_KEY`: Alternative high-quality extraction provider.

---

## How to Run

The pipeline is orchestrated by a single command-line tool: `run_pipeline.py`. 

### Basic Usage

To run the full extraction pipeline for a university:

```bash
python run_pipeline.py --university "https://www.lmu.de/en/"
```

### Options

| Flag | Description |
|------|-------------|
| `--university` | **(Required)** The base URL of the university. |
| `--programs` | Limit the number of programmes to process. Great for testing. (e.g. `--programs 5`) |
| `--country` | Provide a country name for the workspace structure (e.g. `--country Germany`). If omitted, it will try to infer it from the URL domain (e.g. `.de` -> `germany`). |
| `--workspace` | The root folder where all data will be saved. Default is `data`. |
| `--continue-on-error` | If provided, the pipeline will skip programmes that fail and continue to the next one. Without this, the pipeline stops on the first error. |
| `--verbose` | Print extra debug and execution information. |

### Examples

**1. Test a single programme (Recommended for first run):**
```bash
python run_pipeline.py --university "https://www.lmu.de/en/" --programs 1
```

**2. Process 10 programmes and save to a specific directory:**
```bash
python run_pipeline.py --university "https://www.lmu.de/en/" --programs 10 --workspace "./test_output"
```

**3. Run a massive crawl overnight and don't stop if one programme fails:**
```bash
python run_pipeline.py --university "https://www.lmu.de/en/" --continue-on-error
```

---

## Output Structure

The system generates a detailed directory structure to preserve evidence at every step. By default, this is stored in `data/universities/`:

```text
data/
└── universities/
    └── <university-name>/
        ├── discovery.json                 # Output of Phase 1 (Programme Discovery)
        └── programs/
            ├── 0001/
            │   ├── webpage/               # Raw HTML and converted Markdown
            │   ├── evidence/              # Manifests and child pages
            │   ├── facts/                 # LLM outputs (raw and normalized JSON)
            │   └── final/                 # Validated, consumer-ready JSON files
            ├── 0002/
            └── ...
```

## Testing

The project includes a suite of tests to verify extraction quality and data preservation.

```bash
python test_program_extractor.py
python test_semantic_normalizer.py
python test_final_output_builder.py
python test_qs_profile_extractor.py
python test_qs_ranking_extractor.py
python test_qs_output_builder.py
```
