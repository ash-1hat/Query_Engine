# Query Engine

An AI-powered expert system that leverages OpenAI's vectorStores API and GPT-4o to provide domain-specific knowledge and expertise.

## Features

- Expert-based knowledge retrieval using vector search
- Multiple memory types (LLM, Domain, Expert, Client)
- Document parsing and indexing
- Citation support for responses
- FastAPI backend with Supabase integration

## Architecture

- **Backend**: FastAPI, Python 3.13
- **Database**: Supabase
- **AI**: OpenAI GPT-4o, vectorStores API
- **Document Processing**: LlamaParse

## Memory Types

1. **LLM Memory**: Uses OpenAI directly without vector search
2. **Domain Memory**: Uses domain's default_vector_id
3. **Expert Memory**: Uses expert's preferred_vector_id
4. **Client Memory**: Uses client-specific vector store

## API Endpoints

- `/api/query`: Query experts with specific memory types
- `/api/experts`: Manage expert profiles
- `/api/domains`: Manage knowledge domains
- `/api/vectors`: Manage vector stores and memory
