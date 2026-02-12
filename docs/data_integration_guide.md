# Data Integration Guide: 3ioNetra Spiritual Companion

This document outlines the process, risks, and strategies for integrating new spiritual datasets into the 3ioNetra platform.

---

## 1. Overview of Data Ingestion

3ioNetra uses a Retrieval-Augmented Generation (RAG) pipeline. Integrating new data involves transforming raw spiritual texts into structured, embedded chunks that the system can retrieve during conversations.

### 1.1 Current Process (JSON/CSV)

The existing ingestion pipeline (`backend/scripts/ingest_all_data.py`) follows these steps:
1.  **Normalization**: Raw files (CSV/JSON) are parsed. Common fields like `chapter`, `verse`, and `text` are mapped.
2.  **Cleaning**: Content is stripped of markdown and excessive whitespace.
3.  **Deduplication**: Verses are deduplicated based on a unique `reference` key (e.g., "Bhagavad Gita 2.47").
4.  **Embedding**: Text is converted into 768-dimensional vectors using `paraphrase-multilingual-mpnet-base-v2`.
5.  **Consolidation**: All data is saved into a primary `processed_data.json` for the RAG engine.

---

## 2. Integration of Diverse Sources & Formats

To evolve 3ioNetra into a production-grade system, we are implementing support for complex data types.

### 2.1 Handling Different Formats

| Format | Processing Strategy | Implementation Detail |
| :--- | :--- | :--- |
| **PDF** | Structure-Aware Parsing | Use `PyMuPDF` or `Unstructured.io` to distinguish between main text, footnotes, and headers in original scripts. |
| **HTML/Web** | Headless Crawling | Use `Firecrawl` or `BeautifulSoup` to scrape blogs and temple websites while stripping non-spiritual elements (ads, nav). |
| **Markdown** | Direct Parsing | Leveraging YAML frontmatter for metadata (Deity, Philosophy) and splitting by header hierarchy. |

### 2.2 Handling Different Sources

| Source | Integration Method | Security/Risk |
| :--- | :--- | :--- |
| **Local File Upload** | Batch Processing CLI | Low risk; files validated before hashing and indexing. |
| **Web Crawling** | Periodic Sync Bot | Medium risk (rate limiting, stale data). Requires a checksum-based skipping logic. |
| **Third-Party APIs** | Real-time / Caching | High reliance on uptime. Example: Panchang API integrated via LLM Function Calling. |

---

## 3. Risk & Mitigation Documentation

Integrating large-scale spiritual data carries specific risks that must be managed to maintain the bot's "Mitra" (friend) persona and accuracy.

| Risk Category | Specific Risk | Mitigation Strategy |
| :--- | :--- | :--- |
| **Accuracy** | Overlapping or contradictory guidance from different regional traditions. | Implement **Metadata Tagging** (e.g., "Advaita", "Bhakti") to allow LLM to provide context-aware responses. |
| **Scale** | Vector DB bloat and slow retrieval as dataset grows. | Transition to **Hybrid Search** (Vector + BM25) and implement **Incremental Ingestion** (skipping unchanged files). |
| **Quality** | Poor quality OCR or garbled Sanskrit transliterations. | Implement a **Validation Stage** in the ingestion script using LLM-based quality checks before embedding. |
| **Relevance** | Retrieval of "generic" verses that don't address specific user pain points. | Use **Neural Reranking** and **Semantic Chunking** instead of fixed-size window splits. |
| **Safety** | User sharing crisis signals while bot retrieves ancient text instead of crisis resources. | Maintain a **Hard-coded Safety Layer** that overrides RAG retrieval when crisis keywords are detected. |

---

## 4. Step-by-Step Integration Process for New Datasets

1.  **Schema Alignment**: Ensure the new dataset is converted to the standard JSON structure (`id`, `scripture`, `chapter`, `verse_number`, `text`).
2.  **Preprocessing**: Run the standard markdown stripper and whitespace cleaner.
3.  **Reference Generation**: Construct unique references to avoid polluting the database with duplicates.
4.  **Validation Run**: Ingest a sample (20-50 items) and perform a manual check for embedding accuracy.
5.  **Full Ingestion**: Execute `ingest_all_data.py`.
6.  **RAG Verification**: Run the `test_rag.py` script to ensure the new data is retrieved for relevant queries.
