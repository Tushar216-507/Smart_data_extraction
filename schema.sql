-- ==============================================================================
-- Smart Data Extraction — Database Schema (MySQL)
-- ==============================================================================
--
-- Hierarchy:
--   countries → universities → programs
--                    ↓              ↓
--            university_data   program_data
--
-- The exporter walks data/<country>/<university>/discovery.json
-- and data/<country>/<university>/programs/<code>/final/*.json
-- to populate these tables.
--
-- This schema is country-agnostic and university-agnostic.
-- It works for any country, any university, any number of programs.
-- ==============================================================================


-- ------------------------------------------------------------------------------
-- 1. Countries
-- ------------------------------------------------------------------------------
-- One row per country folder found under data/.
-- Example slugs: united_kingdom, canada, germany, india
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS countries (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    slug            VARCHAR(255) NOT NULL UNIQUE COMMENT 'Folder name under data/, e.g. united_kingdom',
    display_name    VARCHAR(255) COMMENT 'Human-readable name, e.g. United Kingdom',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------------------------
-- 2. Universities
-- ------------------------------------------------------------------------------
-- One row per university folder found under data/<country>/.
-- Metadata comes from discovery.json and metadata.json.
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS universities (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    country_id      INT NOT NULL,
    slug            VARCHAR(255) NOT NULL COMMENT 'Folder name, e.g. imperialac, utoronto',
    name            VARCHAR(512) NOT NULL COMMENT 'Full university name',
    base_url        VARCHAR(2048) NOT NULL COMMENT 'From discovery.json university_base_url',
    total_programs  INT DEFAULT 0 COMMENT 'From discovery.json total_working_program_urls',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
    UNIQUE KEY uq_university_identity (country_id, slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------------------------
-- 3. Programs
-- ------------------------------------------------------------------------------
-- One row per program entry in discovery.json.
-- Fields come directly from the program_urls[] array in discovery.json.
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS programs (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    university_id       INT NOT NULL,
    program_code        VARCHAR(255) NULL COMMENT 'Folder name, e.g. 0001, 0002',
    url                 VARCHAR(2048) NOT NULL COMMENT 'Full program URL from discovery',
    title               VARCHAR(512) NOT NULL COMMENT 'title field from discovery.json',
    title_original      VARCHAR(512) COMMENT 'title_original from discovery.json',
    title_en            VARCHAR(512) COMMENT 'English-translated title',
    h1                  VARCHAR(512) COMMENT 'h1 heading from discovery.json',
    h1_original         VARCHAR(512) COMMENT 'h1_original from discovery.json',
    h1_en               VARCHAR(512) COMMENT 'English-translated h1',
    page_type           VARCHAR(100) COMMENT 'Classification: Degree Programme, Other, etc.',
    score               INT DEFAULT 0 COMMENT 'Discovery scoring value',
    status              INT NULL COMMENT 'HTTP status code from discovery',
    discovery_reasons   JSON COMMENT 'Array of scoring reasons from discovery.json',
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (university_id) REFERENCES universities(id) ON DELETE CASCADE,
    UNIQUE KEY uq_program_identity (university_id, program_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------------------------
-- 4. University Data
-- ------------------------------------------------------------------------------
-- Stores JSON files from <university>/final/*.json (e.g. qs_data.json).
-- Each file becomes one row. The full JSON content is preserved as-is.
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS university_data (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    university_id   INT NOT NULL,
    category          VARCHAR(255) NOT NULL COMMENT 'Derived from filename, e.g. qs_data',
    source_file     VARCHAR(512) COMMENT 'Original filename, e.g. qs_data.json',
    source_url      VARCHAR(2048) COMMENT 'Provenance URL for the data source',
    raw_json        JSON NOT NULL COMMENT 'Complete JSON content of the file',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (university_id) REFERENCES universities(id) ON DELETE CASCADE,
    UNIQUE KEY uq_university_data_category (university_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ------------------------------------------------------------------------------
-- 5. Program Data
-- ------------------------------------------------------------------------------
-- Stores JSON files from <university>/programs/<code>/final/*.json.
-- Each file becomes one row. The full JSON content is preserved as-is.
--
-- Categories come from filenames:
--   admission_data.json  → category = 'admission'
--   curriculum_data.json → category = 'curriculum'
--   fees_data.json       → category = 'fees'
--   scholarships_data.json → category = 'scholarships'
--   career_data.json     → category = 'career'
--   program_data.json    → category = 'program'
--   research_data.json   → category = 'research'
--   visa_data.json       → category = 'visa'
--   statistics_data.json → category = 'statistics'
--   other_data.json      → category = 'other'
--   build_summary.json   → category = 'build_summary'
--   (any future files are automatically supported)
-- ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS program_data (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    program_id      INT NOT NULL,
    category        VARCHAR(255) NOT NULL COMMENT 'Derived from filename, e.g. admission, curriculum',
    source_file     VARCHAR(512) COMMENT 'Original filename, e.g. admission_data.json',
    source_url      VARCHAR(2048) COMMENT 'Provenance URL for the data source',
    fact_count      INT DEFAULT 0 COMMENT 'Number of facts in this file',
    raw_json        JSON NOT NULL COMMENT 'Complete JSON content of the file',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (program_id) REFERENCES programs(id) ON DELETE CASCADE,
    UNIQUE KEY uq_program_data_category (program_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
