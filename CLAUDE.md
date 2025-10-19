# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Clone is a RAG (Retrieval-Augmented Generation) system for healthcare organizations, specifically designed for the 1hat.in ecosystem. It creates AI expert clones that mimic real doctors' expertise using OpenAI's vectorStores API and GPT-4o.

## Development Commands

### Backend (FastAPI)

**Start the API server:**
```bash
cd src/api
python main.py
```
This starts the FastAPI server on `http://0.0.0.0:8080` with hot reload enabled.

**Alternative start (from project root):**
```bash
cd "AI Clone/src/api" && python main.py
```

### Frontend (Streamlit)

**Start the Streamlit UI:**
```bash
cd src/ui
streamlit run app.py
```

### Environment Setup

**Create .env file from template:**
```bash
cp .env.example .env
```

**Required environment variables:**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `OPENAI_API_KEY` - OpenAI API key
- `LLAMAPARSE_API_KEY` - LlamaParse API key for document parsing
- `DOMAIN_FILE_PATH` (optional) - Path to domain configuration JSON file

**Install dependencies:**
```bash
pip install -r requirements.txt
```

## Architecture Overview

### Multi-Level Memory System

The system implements a hierarchical memory architecture with four distinct levels:

1. **LLM Memory** (`memory_type="llm"`)
   - Direct OpenAI calls without vector search
   - No document retrieval, pure language model responses

2. **Organization Memory** (`memory_type="organization"`)
   - Hospital/organization-wide knowledge base
   - Accessible across all domains and experts

3. **Domain Memory** (`memory_type="domain"`)
   - Specialty-specific knowledge (e.g., cardiology, pediatrics)
   - Shared across all experts within that domain
   - Located at: `src/api/endpoints.py:initialize_domains`

4. **Expert Memory** (`memory_type="expert"`)
   - Individual doctor's specialized knowledge and documents
   - Includes AI-generated persona from Q&A pairs
   - Located at: `src/api/endpoints.py:initialize_expert_memory`

5. **Client Memory** (`memory_type="client"`)
   - Organization-wide patient information accessible to all relevant experts
   - Stores consultation history with timestamps

6. **MyClient Memory** (`memory_type="myclient"`)
   - Expert-specific patient information
   - Only accessible to the associated expert

### Key Database Schema (Supabase)

**Organizations**: `org_name`, `id`

**Domains**: `domain_name`, `expert_names[]`, `org_id`

**Experts**: `name`, `domains[]`, `context` (AI-generated persona), `org_id`

**Clients**: `client_name`, `org_client_id`, `client_data_jsonb`, `org_id`, `expert_id`
- Uses history-preserving merge strategy in `src/api/endpoints.py:history_preserving_merge`
- Each update preserves full consultation history in `_history` field

**Documents**: `name`, `document_link`, `openai_file_id`, `owner_id`, `doc_type`

**Vector Stores**: `vector_id` (OpenAI), `vector_name`, `file_ids[]`, `batch_ids[]`, `org_id`, `owner` (memory type), `domain_id`, `expert_id`, `client_id`

**Assistants**: Cached OpenAI assistant configurations keyed by `memory_type` and `vector_name`

### Core Workflows

**Creating an Expert Clone:**
```
1. Initialize org → POST /api/memory/org/initialize
2. Create domain(s) → POST /api/domains/initialize
3. Create expert with Q&A pairs → POST /api/memory/expert/initialize
   - Generates persona using GPT-4o from Q&A pairs (utils.py:generate_persona_from_qa)
   - Creates expert vector store
   - Uploads documents to vector store
4. Expert is ready to query
```

**Querying an Expert:**
```
1. User sends query → POST /api/query-clone
2. Get/create OpenAI Assistant (utils.py:get_or_create_assistant)
3. Create or continue thread
4. Add message to thread
5. Run assistant with file_search tool
6. Return response with citations removed (utils.py:get_assistant_response)
```

**Adding a Patient (1hat workflow):**
```
POST /api/1hat/add-patient
→ Creates org → domain → expert → client (both org-level and expert-level)
→ Initializes vector stores with patient data as JSONB documents
```

## Important Code Locations

### API Entry Point
`src/api/main.py:37` - Main FastAPI application entry point

### Memory Initialization
- Org memory: `src/api/endpoints.py:initialize_org_memory`
- Domain memory: `src/api/endpoints.py:initialize_domains`
- Expert memory: `src/api/endpoints.py:initialize_expert_memory`
- Client memory: `src/api/endpoints.py:initialize_client_memory`

### Core Query Logic
- Main query endpoint: `src/api/endpoints.py:query_clone`
- Assistant integration: `src/api/utils.py:query_expert_with_assistant`
- Response extraction: `src/api/utils.py:get_assistant_response`

### Document Processing
- Vector store creation: `src/api/utils.py:create_vector_store`
- File creation from URLs: `src/api/utils.py:create_file_for_vector_store`
  - Supports: Web URLs, YouTube transcripts, local files, PDFs
  - Has retry logic with exponential backoff (lines 217-311)
- Batch upload: `src/api/utils.py:add_documents_to_vector_store`
- Vector store editing: `src/api/utils.py:edit_vector_store`

### Persona Generation
`src/api/utils.py:generate_persona_from_qa` - Converts Q&A pairs into expert persona using GPT-4o

### Client Data Management
`src/api/endpoints.py:history_preserving_merge` - Merges new patient data while preserving full consultation history

## Special Considerations

### Always Ask Before Editing
Per user instructions in `~/.claude/CLAUDE.md`, always ask before making edits to main files under `src/` folder.

### File Path Resolution
Document processing tries multiple base directories when resolving local file paths:
- Current working directory
- Script directory
- Project root
- `Docs/` folder
- `data/` folder
- `documents/` folder

Located at: `src/api/utils.py:320-326`

### Accepted File Extensions
```python
['.c', '.cpp', '.css', '.csv', '.doc', '.docx', '.gif', '.go', '.html',
 '.java', '.jpeg', '.jpg', '.js', '.json', '.md', '.pdf', '.php', '.pkl',
 '.png', '.pptx', '.py', '.rb', '.tar', '.tex', '.ts', '.txt', '.webp',
 '.xlsx', '.xml', '.zip']
```

### Document URL Validation
URLs are validated before processing in `src/api/utils.py:check_document_urls` to ensure they have accepted file extensions.

### Citation Removal
Assistant responses automatically strip OpenAI citation markers (e.g., `【4:6†source】`) using regex in `src/api/utils.py:1749`.

### Memory Type Routing
The system uses a match-case statement to route vector store queries based on `memory_type`:
- Located at: `src/api/utils.py:get_query_for_vector_store`
- Critical for determining which vector store to query

### Domain Configuration File
Optional JSON file for batch domain/document loading:
```json
{
  "domains": [
    {
      "domain_name": "Cardiology",
      "files": [
        {"file_name": "Heart Conditions", "url": "https://example.com/doc.pdf"}
      ]
    }
  ]
}
```
Parser: `src/api/utils.py:parse_domain_config_file`

## Common Gotchas

1. **Owner ID for Documents**: Different memory types use different owner IDs:
   - Domain: uses `domain_id`
   - Expert: uses `expert_id`
   - Client: uses `client_id`
   - MyClient: uses `"{expert_id}_{client_id}"`

2. **Vector Name Format**: Vector names are based on UUIDs or concatenated IDs depending on memory type (see `utils.py:get_query_for_vector_store`)

3. **Assistant Caching**: Assistants are cached in Supabase and retrieved by `vector_name` to avoid recreating them on every query

4. **File Deduplication**: The system checks for existing documents by URL and owner_id before uploading to prevent duplicates (`utils.py:166-173`)

5. **History Tracking**: Patient data updates create snapshots in `_history` array with `consultation_id` and `created_time` for audit trails

6. **JSON Document Storage**: Patient JSONB data is converted to JSON files and uploaded to vector stores for RAG retrieval

## Testing

The project currently has no test files in `src/`. Dependencies include test suites but the main application code does not have dedicated tests.

## Server Configuration

- **Host**: `0.0.0.0` (accepts connections from any IP)
- **Port**: `8080`
- **Reload**: Enabled (auto-restarts on code changes)
- **CORS**: Allows all origins, methods, and headers
- always add new functions in this project. Do not disturb existing functionality unless it is redundant in which case, let me know before removing or making changing to existing functions
- always ask before finalizing code changes so I can review and finalize. If documentation changes, do not ask but just make those changes.