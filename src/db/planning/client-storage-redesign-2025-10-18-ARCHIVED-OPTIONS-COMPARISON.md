# Client/Patient Data Storage Redesign
**Session Date:** October 18, 2025
**Branch:** t3
**Status:** Planning Phase - Awaiting Final Decision

---

## Executive Summary

This document outlines a comprehensive redesign of the client/patient data storage system to optimize for:
1. **RAG (Retrieval-Augmented Generation) performance** - Better retrieval quality for AI queries
2. **Export flexibility** - Easy CSV and HL7 format exports
3. **Query performance** - Fast access to consultation history
4. **Scalability** - Support growing patient data over time

---

## Current System Analysis

### Database Schema

**`clients` Table:**
- Stores patient demographic and consultation data
- Two records per patient:
  - Org-level (expert_id = NULL) - accessible to all experts
  - Expert-level (expert_id = specific expert ID)
- `client_data_jsonb` (JSONB) - Contains ALL consultation history with `_history[]` array

**`vector_stores` Table:**
- Tracks OpenAI vector stores
- Links to clients via `client_id`
- Stores `file_ids[]` array

**`documents` Table:**
- Tracks individual files uploaded to OpenAI
- `openai_file_id` - Reference to OpenAI file
- `doc_type` - e.g., "json", "link", "pdf"

### Current Data Flow

1. **Initial patient creation** (`/1hat/add-patient`):
   - Creates 2 client records (org-level + expert-level)
   - Creates 2 vector stores ("client" + "myclient" memory types)
   - Creates JSON files from `client_data_jsonb`
   - File naming: `{consultation_id}_{org/expert_id}_{client_id}`

2. **Patient updates** (subsequent calls):
   - `create_update_client()` updates database JSONB only
   - Uses `history_preserving_merge()` to append to `_history[]`
   - **Vector store files are NOT updated** ⚠️

### Critical Problems Identified

1. **Stale Vector Store Data**
   - Database JSONB updates but vector store files remain unchanged
   - AI retrieves outdated patient information
   - Growing disconnect between DB and RAG data

2. **Poor RAG Performance**
   - Single large JSONB file with entire patient history
   - LLM must process entire history for simple queries
   - Reduced retrieval precision and relevance

3. **Difficult Exports**
   - Need to traverse nested JSONB `_history[]` arrays
   - No structured fields for direct CSV/HL7 mapping
   - Complex transformation logic required

4. **Scalability Issues**
   - JSONB grows indefinitely
   - File size increases with each consultation
   - Slower processing over time

---

## Architectural Options

### Comparison Table

| Approach | RAG Performance | CSV Export | Query Speed | Migration Effort | Storage Efficiency |
|----------|----------------|------------|-------------|------------------|-------------------|
| **Current** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | N/A | ⭐⭐ |
| **Option A (Recommended)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Option B (Event Sourcing)** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Option C (Document-Oriented)** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Option D (Time-Series)** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |

### Detailed Comparison

| Feature | Option A | Option B | Option C | Option D |
|---------|----------|----------|----------|----------|
| **RAG - Single Consultation** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **RAG - Patient History** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **CSV Export** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **HL7 Export** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Query: Recent Consultations** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Query: Specific Field** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Migration Effort** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| **Storage Efficiency** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Schema Complexity** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Future Extensibility** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Vector File Count** | Moderate | High | Moderate | High |
| **Audit Trail** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

---

## Option A: Hybrid with Consultations Table ⭐ RECOMMENDED

### Overview
Separate patient demographics from consultation history into dedicated tables with structured fields for optimal querying and RAG performance.

### Database Schema

```sql
-- Modified clients table (demographics + current state)
CREATE TABLE IF NOT EXISTS clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_name TEXT NOT NULL,
    org_id UUID NOT NULL,
    expert_id UUID,  -- NULL for org-level, specific for expert-level
    org_client_id INT NOT NULL,

    -- Current/Latest snapshot fields (extracted for fast queries)
    current_diagnosis TEXT,
    current_medications JSONB,
    current_vitals JSONB,
    last_consultation_id UUID,
    last_updated TIMESTAMP WITH TIME ZONE,

    -- Demographic info (rarely changes)
    demographics JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES organizations (id)
);

-- NEW: Consultations table (one row per consultation)
CREATE TABLE IF NOT EXISTS consultations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id TEXT NOT NULL UNIQUE,  -- From 1hat
    client_id UUID NOT NULL,  -- Links to clients.id
    org_client_id INT NOT NULL,  -- Denormalized for faster queries
    expert_id UUID NOT NULL,
    org_id UUID NOT NULL,

    -- Structured fields for fast queries & CSV export
    consultation_date TIMESTAMP WITH TIME ZONE,
    chief_complaint TEXT,
    diagnosis TEXT,
    treatment_plan TEXT,
    medications JSONB,  -- Array of {name, dosage, frequency}
    vitals JSONB,  -- {bp, temp, pulse, etc.}
    lab_results JSONB,
    prescriptions JSONB,
    notes TEXT,

    -- Full consultation data (for completeness)
    full_data JSONB NOT NULL,

    -- Metadata
    created_time TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_client FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE,
    CONSTRAINT fk_expert FOREIGN KEY (expert_id) REFERENCES experts (id),
    CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES organizations (id)
);

-- Indexes for fast retrieval
CREATE INDEX idx_consultations_client ON consultations (client_id, consultation_date DESC);
CREATE INDEX idx_consultations_org_client ON consultations (org_client_id, org_id);
CREATE INDEX idx_consultations_expert ON consultations (expert_id, consultation_date DESC);
CREATE INDEX idx_consultations_date ON consultations (consultation_date DESC);
CREATE INDEX idx_consultations_id ON consultations (consultation_id);
```

### Vector Store Strategy

**Granular Files** - One JSON file per consultation for optimal RAG retrieval:

**File Naming:**
- Org-level: `consultation_{consultation_id}_{org_id}.json`
- Expert-level: `consultation_{consultation_id}_{expert_id}.json`

**File Size:** Small (~2-10KB per consultation)

**File Content Structure:**
```json
{
  "consultation_id": "CONS-2025-001",
  "patient_name": "John Doe",
  "org_client_id": 12345,
  "consultation_date": "2025-10-18T10:30:00Z",
  "chief_complaint": "Persistent headache for 3 days",
  "diagnosis": "Tension headache",
  "medications": [
    {"name": "Ibuprofen", "dosage": "400mg", "frequency": "TID"}
  ],
  "vitals": {
    "bp": "120/80",
    "temp": "98.6F",
    "pulse": 72
  },
  "lab_results": {},
  "notes": "Patient reports stress at work. Recommended relaxation techniques.",
  "treatment_plan": "OTC pain relief, stress management counseling",
  "patient_context": {
    "age": 45,
    "gender": "M",
    "chronic_conditions": ["None"]
  },
  "full_data": { /* Complete JSONB if needed */ }
}
```

### RAG Retrieval Flow

**Query Example:** "What medications was patient 12345 prescribed in the last month?"

**Process:**
1. System queries `consultations` table:
   ```sql
   SELECT consultation_id, medications, consultation_date
   FROM consultations
   WHERE org_client_id = 12345
     AND consultation_date > NOW() - INTERVAL '1 month'
   ORDER BY consultation_date DESC;
   ```
2. Returns focused list of consultation IDs
3. OpenAI retrieves relevant consultation files from vector store
4. LLM processes small, focused documents
5. High relevance and precision

**Benefits:**
- ✅ Small document size = better embeddings
- ✅ Focused retrieval = higher precision
- ✅ Can query specific time ranges
- ✅ Can filter by diagnosis, medication, etc.

### CSV Export Implementation

**Direct SQL Query:**
```sql
-- Export all consultations for a patient
SELECT
    c.consultation_id,
    cl.client_name,
    c.consultation_date,
    c.chief_complaint,
    c.diagnosis,
    c.medications::text,
    c.vitals::text,
    c.treatment_plan,
    c.notes
FROM consultations c
JOIN clients cl ON c.client_id = cl.id
WHERE c.org_client_id = 12345
ORDER BY c.consultation_date DESC;
```

**Python Export Function:**
```python
async def export_to_csv(org_client_id: int, date_range: Optional[dict] = None,
                        fields: Optional[list] = None):
    """
    Export patient consultations to CSV

    Args:
        org_client_id: Patient ID from 1hat
        date_range: {"start": "2025-01-01", "end": "2025-12-31"}
        fields: ["consultation_date", "diagnosis", "medications", ...]

    Returns:
        CSV file content
    """
    query = supabase.table("consultations").select("*")
    query = query.eq("org_client_id", org_client_id)

    if date_range:
        query = query.gte("consultation_date", date_range["start"])
        query = query.lte("consultation_date", date_range["end"])

    result = query.execute()

    # Convert to CSV using pandas
    df = pd.DataFrame(result.data)

    if fields:
        df = df[fields]

    return df.to_csv(index=False)
```

### HL7 Export Implementation

```python
async def export_to_hl7(consultation_id: str, hl7_version: str = "2.5"):
    """
    Export consultation to HL7 format

    Args:
        consultation_id: Specific consultation ID
        hl7_version: HL7 version (e.g., "2.5", "2.7")

    Returns:
        HL7 message string
    """
    # Fetch consultation data
    result = supabase.table("consultations").select("*").eq(
        "consultation_id", consultation_id
    ).execute()

    data = result.data[0]

    # Transform to HL7 format (using hl7apy or custom mapper)
    from hl7apy.core import Message

    msg = Message("ORM_O01", version=hl7_version)
    msg.msh.msh_3 = "AI_CLONE"
    msg.msh.msh_4 = data["org_id"]

    # Add patient segment
    msg.add_segment("PID")
    msg.pid.pid_3 = data["org_client_id"]
    msg.pid.pid_5 = data["client_name"]

    # Add observation segments
    obr = msg.add_segment("OBR")
    obr.obr_4 = data["diagnosis"]

    # Add medications
    for med in data["medications"]:
        rxe = msg.add_segment("RXE")
        rxe.rxe_2 = med["name"]
        rxe.rxe_3 = med["dosage"]

    return str(msg)
```

### Data Migration Strategy

**Phase 1: Create New Tables**
```sql
-- Run schema updates
\i src/db/schema_updates_consultations.sql
```

**Phase 2: Migrate Existing Data**
```python
async def migrate_clients_to_consultations():
    """
    Migrate existing client_data_jsonb to consultations table
    """
    # Fetch all clients
    clients = supabase.table("clients").select("*").execute()

    for client in clients.data:
        client_id = client["id"]
        org_client_id = client["org_client_id"]
        expert_id = client["expert_id"]
        org_id = client["org_id"]

        jsonb_data = client["client_data_jsonb"]

        if not jsonb_data:
            continue

        # Extract demographics
        demographics = extract_demographics(jsonb_data)

        # Process history entries
        if "_history" in jsonb_data:
            for history_entry in jsonb_data["_history"]:
                await create_consultation_from_history(
                    client_id=client_id,
                    org_client_id=org_client_id,
                    expert_id=expert_id,
                    org_id=org_id,
                    history_data=history_entry["data"],
                    consultation_id=history_entry["consultation_id"],
                    created_time=history_entry["created_time"]
                )

        # Process current consultation (not in history)
        current_consultation_id = jsonb_data.get("consultation_id")
        if current_consultation_id:
            await create_consultation_from_history(
                client_id=client_id,
                org_client_id=org_client_id,
                expert_id=expert_id,
                org_id=org_id,
                history_data=jsonb_data,
                consultation_id=current_consultation_id,
                created_time=jsonb_data.get("created_time")
            )

        # Update client with demographics only
        await supabase.table("clients").update({
            "demographics": demographics,
            "client_data_jsonb": None  # Clear old JSONB
        }).eq("id", client_id).execute()

async def create_consultation_from_history(client_id, org_client_id,
                                          expert_id, org_id, history_data,
                                          consultation_id, created_time):
    """
    Create consultation record and vector store file from history entry
    """
    # Extract structured fields
    extracted = extract_consultation_fields(history_data)

    # Insert into consultations table
    consultation = {
        "consultation_id": consultation_id,
        "client_id": client_id,
        "org_client_id": org_client_id,
        "expert_id": expert_id,
        "org_id": org_id,
        "consultation_date": created_time,
        "chief_complaint": extracted.get("chief_complaint"),
        "diagnosis": extracted.get("diagnosis"),
        "treatment_plan": extracted.get("treatment_plan"),
        "medications": extracted.get("medications"),
        "vitals": extracted.get("vitals"),
        "lab_results": extracted.get("lab_results"),
        "prescriptions": extracted.get("prescriptions"),
        "notes": extracted.get("notes"),
        "full_data": history_data,
        "created_time": created_time
    }

    result = await supabase.table("consultations").insert(consultation).execute()

    # Create vector store files
    await create_consultation_vector_files(
        consultation_id=consultation_id,
        org_id=org_id,
        expert_id=expert_id,
        consultation_data=consultation
    )
```

**Phase 3: Update Application Code**
- Modify `/1hat/add-patient` endpoint to use new schema
- Update `create_update_client()` to write to consultations table
- Create vector files on every consultation insert/update

**Phase 4: Verify and Clean Up**
- Verify data integrity
- Remove old `client_data_jsonb` column
- Archive old vector store files

### Implementation Tasks

**Backend Changes:**

1. **Create schema migration file** (`src/db/schema_updates_consultations.sql`)
   - Add `consultations` table
   - Add indexes
   - Modify `clients` table

2. **Create field extraction utility** (`src/api/utils.py`)
   ```python
   async def extract_consultation_fields(jsonb_data: dict) -> dict:
       """
       Extract structured fields from JSONB consultation data

       Uses configurable field mappings to handle varying JSONB structures
       """
       FIELD_MAPPINGS = {
           "diagnosis": ["diagnosis", "provisional_diagnosis", "final_diagnosis"],
           "medications": ["medications", "prescriptions", "drugs", "meds"],
           "vitals": ["vitals", "vital_signs", "measurements"],
           "chief_complaint": ["chief_complaint", "cc", "presenting_complaint"],
           # ...
       }

       extracted = {}
       for field, possible_keys in FIELD_MAPPINGS.items():
           for key in possible_keys:
               if key in jsonb_data:
                   extracted[field] = jsonb_data[key]
                   break

       return extracted
   ```

3. **Create consultation manager** (`src/api/consultation_manager.py`)
   - `create_consultation()`
   - `update_consultation()`
   - `get_consultations()`
   - `sync_consultation_to_vector_store()`

4. **Modify endpoints** (`src/api/endpoints.py`)
   - Update `/1hat/add-patient` to use consultations table
   - Update `create_update_client()` to create consultation records
   - Add vector file sync after consultation creation

5. **Add export endpoints** (`src/api/endpoints.py`)
   ```python
   @router.get("/export/csv/{org_client_id}")
   async def export_patient_csv(org_client_id: int, ...)

   @router.get("/export/hl7/{consultation_id}")
   async def export_consultation_hl7(consultation_id: str, ...)
   ```

### Pros ✅

- **Excellent RAG performance**: Small, focused documents per consultation
- **Lightning-fast exports**: Direct SQL to CSV/HL7 with structured columns
- **Fast queries**: Indexed fields, no JSON traversal needed
- **Scalable**: Can partition by date for millions of consultations
- **Flexible**: Easy to add new structured fields
- **Moderate migration**: Can run incrementally, no downtime required
- **Audit trail**: Full history preserved in `full_data` JSONB
- **Future-proof**: Easy to add FHIR, CDA exports later

### Cons ❌

- **Migration required**: Need to transform existing data
- **Field extraction logic**: Must maintain mappings for varying JSONB structures
- **Data duplication**: Structured fields + full JSONB (acceptable trade-off)
- **Initial effort**: Schema changes + code updates

---

## Option B: Event Sourcing Pattern

### Overview
Store all patient data as immutable event log. Current state is derived from replaying events.

### Database Schema

```sql
-- Immutable event log
CREATE TABLE IF NOT EXISTS patient_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_client_id INT NOT NULL,
    expert_id UUID,
    org_id UUID NOT NULL,

    event_type TEXT NOT NULL,
    -- Examples: 'consultation_started', 'diagnosis_added',
    --           'medication_prescribed', 'vital_recorded'

    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    consultation_id TEXT,

    payload JSONB NOT NULL,  -- Event-specific data

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Materialized view for current state (updated via triggers)
CREATE TABLE IF NOT EXISTS patient_snapshots (
    org_client_id INT PRIMARY KEY,
    org_id UUID NOT NULL,
    current_state JSONB,
    last_event_id UUID,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_events_client ON patient_events (org_client_id, event_timestamp DESC);
CREATE INDEX idx_events_consultation ON patient_events (consultation_id);
CREATE INDEX idx_events_type ON patient_events (event_type);
```

### Example Event Flow

```json
// Event 1: Consultation started
{
  "event_type": "consultation_started",
  "consultation_id": "CONS-001",
  "payload": {
    "patient": {"name": "John Doe", "age": 45},
    "timestamp": "2025-10-18T10:00:00Z"
  }
}

// Event 2: Chief complaint recorded
{
  "event_type": "chief_complaint_recorded",
  "consultation_id": "CONS-001",
  "payload": {
    "complaint": "Persistent headache for 3 days"
  }
}

// Event 3: Diagnosis made
{
  "event_type": "diagnosis_made",
  "consultation_id": "CONS-001",
  "payload": {
    "diagnosis": "Tension headache",
    "icd_code": "G44.2"
  }
}
```

### Vector Store Strategy

- One file per **event type** per consultation
- Example files:
  - `consultation_123_diagnosis.json`
  - `consultation_123_medications.json`
  - `consultation_123_vitals.json`
- More granular but more files

### Pros ✅

- **Perfect audit trail**: Every change tracked
- **Time-travel queries**: Reconstruct state at any point
- **Immutability**: Events never change, only append
- **Debugging**: Can replay events to find issues
- **Compliance**: Great for regulatory requirements

### Cons ❌

- **Complex queries**: Need to aggregate events
- **RAG complexity**: Multiple files per consultation
- **Export overhead**: Must reconstruct state from events
- **Learning curve**: Event sourcing is complex
- **Storage**: More rows than Option A

---

## Option C: Document-Oriented (Pure JSONB)

### Overview
Keep everything in JSONB, improve with better indexing and structure.

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS consultation_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id TEXT UNIQUE NOT NULL,
    org_client_id INT NOT NULL,
    expert_id UUID,
    org_id UUID,

    document JSONB NOT NULL,  -- All consultation data in JSONB

    -- GIN index for fast JSONB queries
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- GIN index enables fast JSONB queries
CREATE INDEX idx_consultation_docs_gin ON consultation_documents USING GIN (document);
CREATE INDEX idx_consultation_docs_client ON consultation_documents (org_client_id);
CREATE INDEX idx_consultation_docs_expert ON consultation_documents (expert_id);

-- Can also create indexes on specific JSONB paths
CREATE INDEX idx_consultation_diagnosis ON consultation_documents
    USING GIN ((document -> 'diagnosis'));
```

### Query Example

```sql
-- Find consultations with specific diagnosis
SELECT *
FROM consultation_documents
WHERE document @> '{"diagnosis": "Diabetes Type 2"}'
  AND org_client_id = 12345;

-- Find consultations with specific medication
SELECT *
FROM consultation_documents
WHERE document -> 'medications' @> '[{"name": "Metformin"}]';
```

### Vector Store Strategy

- One file per consultation (entire JSONB)
- Filename: `consultation_{consultation_id}.json`
- Relies on OpenAI's JSON understanding

### Pros ✅

- **Simple schema**: Single table
- **Easy migration**: Almost 1:1 from current system
- **Flexible structure**: No rigid schema enforcement
- **Fast to implement**: Minimal code changes

### Cons ❌

- **CSV export complexity**: Need JSONB → column mapping logic
- **Slower queries**: GIN helps but not as fast as native columns
- **RAG quality**: Depends on JSONB structure consistency
- **Limited query optimization**: Can't index all possible paths

---

## Option D: Time-Series Optimized

### Overview
Store patient data as time-series metrics. Optimized for trend analysis and time-range queries.

### Database Schema

```sql
-- Using partitioned table or TimescaleDB
CREATE TABLE IF NOT EXISTS patient_time_series (
    time TIMESTAMPTZ NOT NULL,
    org_client_id INT NOT NULL,
    expert_id UUID,
    org_id UUID,
    consultation_id TEXT,

    -- Separate column per metric category
    metric_type TEXT NOT NULL,  -- 'vital', 'diagnosis', 'medication', 'lab'
    metric_name TEXT,
    metric_value JSONB,

    PRIMARY KEY (time, org_client_id, metric_type, metric_name)
);

-- If using TimescaleDB extension
SELECT create_hypertable('patient_time_series', 'time');

-- Indexes
CREATE INDEX idx_pts_client ON patient_time_series (org_client_id, time DESC);
CREATE INDEX idx_pts_metric ON patient_time_series (metric_type, time DESC);
```

### Example Data

```sql
-- Blood pressure over time
time                     | org_client_id | metric_type | metric_name | metric_value
------------------------|---------------|-------------|-------------|---------------
2025-10-18 10:00:00+00 | 12345         | vital       | bp          | {"systolic": 120, "diastolic": 80}
2025-09-18 10:00:00+00 | 12345         | vital       | bp          | {"systolic": 125, "diastolic": 82}

-- Medications over time
time                     | org_client_id | metric_type | metric_name | metric_value
------------------------|---------------|-------------|-------------|---------------
2025-10-18 10:00:00+00 | 12345         | medication  | metformin   | {"dosage": "500mg", "frequency": "BID"}
```

### Vector Store Strategy

- Files grouped by time windows and metric types
- Examples:
  - `patient_12345_vitals_2025-10.json`
  - `patient_12345_medications_2025-10.json`
- Great for trend analysis queries

### Pros ✅

- **Lightning-fast time-range queries**
- **Perfect for trend analysis**: "Show BP over last 6 months"
- **Excellent export**: Direct to CSV with time series
- **Built-in data retention**: Can auto-delete old data
- **Compression**: TimescaleDB offers automatic compression

### Cons ❌

- **Weakest RAG performance**: Data too fragmented for context
- **Complex full-consultation queries**: Data scattered across rows
- **Requires TimescaleDB**: Or careful manual partitioning
- **Migration effort**: High - complete restructure needed
- **Not ideal for healthcare**: Consultations are contextual, not just metrics

---

## User Requirements Confirmed

Based on session discussion:

1. ✅ **RAG optimization is critical** - Need small, focused documents
2. ✅ **CSV export required** - Direct field mapping needed
3. ✅ **HL7 export required** - Structured data for healthcare interop
4. ✅ **Auto-sync on updates** - Vector stores must stay current
5. ✅ **Two consultation files**: Org-level + Expert-level
6. ✅ **Historical preservation** - Individual consultation files kept

---

## Recommendation: Option A

**Reasoning:**
- ✅ Best RAG performance with focused, per-consultation documents
- ✅ Easiest CSV/HL7 export with structured columns
- ✅ Fast queries with proper indexing
- ✅ Moderate migration effort (can be done incrementally)
- ✅ Future-proof for additional export formats (FHIR, CDA)
- ✅ Aligns with healthcare data best practices

**Enhancements to Add:**

1. **Smart Field Extraction**
   - Configurable mapping for varying JSONB structures
   - Auto-detect common fields
   - Validation and error handling

2. **Vector File Metadata**
   - Include patient context in each consultation file
   - Add chronic conditions, allergies, demographics
   - Better RAG context

3. **Export Templates**
   - Pre-built CSV templates
   - HL7 v2.5, v2.7 support
   - Future FHIR R4 support

---

## Pending Decisions

**Before proceeding with implementation, need answers to:**

1. ✅ **Architecture confirmed**: Option A selected
2. ❓ **Consultation JSONB structure from 1hat**: What fields are typically present?
3. ❓ **Priority extraction fields**: Which fields are most important?
   - Suggested: diagnosis, medications, vitals, chief_complaint, treatment_plan, lab_results
4. ❓ **HL7 version requirements**: v2.5? v2.7? FHIR?
5. ❓ **Migration timeline**: Run immediately or scheduled?
6. ❓ **Backward compatibility**: Keep old JSONB during transition?

---

## Next Steps

**Once decisions are made:**

1. Create schema migration SQL file
2. Implement field extraction utility
3. Create consultation manager module
4. Update endpoints for new schema
5. Build export functions (CSV, HL7)
6. Write migration script
7. Test on sample data
8. Run migration
9. Update vector store sync logic
10. Deploy and monitor

---

## Session Notes

**What worked well in this session:**
- Thorough analysis of current system
- Clear identification of problems
- Multiple architectural options considered
- Trade-offs evaluated systematically

**Key insights:**
- Large JSONB files hurt RAG performance
- Structured fields enable easy exports
- Granular consultation files improve retrieval
- Option A balances all requirements

**Follow-up session should focus on:**
1. Understanding 1hat JSONB structure
2. Defining field extraction logic
3. Building migration script
4. Implementation planning

---

**End of Planning Document**

---

## How to Resume This Session

When starting a new Claude Code session, say:

> "Review the planning document at `src/db/planning/client-storage-redesign-2025-10-18.md` and pick up where we left off. I'm ready to move forward with Option A."

Or provide answers to the pending questions in the "Pending Decisions" section.
