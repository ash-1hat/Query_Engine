# Client/Patient Data Storage Redesign - ENHANCED
**Session Date:** October 18, 2025
**Branch:** t3
**Status:** Planning Phase - Enhanced Architecture with 1hat Integration
**Version:** 2.2 - Segment-Based RAG with **Expert-Scoped Adaptive Learning** + **Gap Analysis Fixes**
**Last Updated:** October 19, 2025

---

## Executive Summary

This document outlines an **enhanced** redesign of the client/patient data storage system, incorporating the 1hat/Pradhi segment-based architecture. This is **significantly better** than the original Option A due to leveraging pre-segmented medical record data.

### Core Objectives

1. **RAG Performance** - Ultra-granular segment-level vector files for precise retrieval
2. **Advanced Search** - Semantic search + composite filter queries + analytics
3. **Expert-Scoped Edit Tracking** - Track edits with **per-expert** adaptive learning (isolated, no cross-expert influence)
4. **EHR Integration** - Configurable field mappings for HL7/JSON/FHIR export
5. **Record Merging** - Flexible merging strategies for longitudinal patient views
6. **Analytics Support** - Support all medical specialties with rich structured fields

### 🔐 **Critical Design Principle: Expert-Level Isolation**

**Each expert's edits and learned patterns are completely isolated:**
- Dr. Smith's corrections only affect Dr. Smith's future AI-generated consultations
- Dr. Jones's preferences remain separate and don't influence Dr. Smith
- No domain-level or hospital-level pattern sharing
- Privacy-preserving: Experts maintain their unique clinical style

---

## User Requirements Confirmed

### Functional Requirements

✅ **1. Effective Multi-Modal Search:**
- **Semantic search**: "What did the patient mainly complain about?"
- **Composite filters**: "In the last 6 months, how many babies were born pre-maturely?"
- **Analytics**: "How many consultations resulted in lower anxiety than when patients walked in?"

✅ **2. Edit Tracking & Expert-Scoped Adaptive Learning:** ⭐ UPDATED
- Compare `original_content` vs `edited_content`
- Word-level diff analysis **per expert**
- Pattern recognition **isolated per expert**
- Feedback incorporation into **only that expert's** future consultations
- **No cross-contamination** between experts

✅ **3. Configurable EHR Export:**
- Field-level export control
- Multiple format support (HL7 v2.5, v2.7, FHIR R4, JSON)
- Specialty-specific mapping configurations

✅ **4. Flexible Record Merging:**
- Follow-up consultation chains
- Master patient summaries
- Configurable merge strategies per use case

### Data Requirements

✅ **Priority Extraction Fields:**

**Clinical:**
- Chief complaint
- Diagnosis
- Medications
- Vital signs
- Treatment plan
- Lab results
- Prescriptions
- Patient history

**Psychosocial:** ⭐ NEW
- Anxiety level (pre-consultation)
- Anxiety level (post-consultation)
- Financial considerations
- Compliance likelihood

**Demographics:**
- Patient name, DOB, age, gender
- Consultation date
- Height, weight

✅ **Backward Compatibility:**
- Keep `client_data_jsonb` column during transition

---

## 1hat/Pradhi Architecture

### Data Structure

**26 Segment Types** received via webhook in single payload:

| Storage Format | Count | Segments |
|---------------|-------|----------|
| **TEXT** | 15 | Summary, Analysis, Key Facts, Timestamped Transcription, Chief Complaint(s), Associated Symptoms, Diagnosis, Additional Observations, Start Date, Context, Investigation, History, Examination |
| **FORMATTED** | 11 | Present Illness Information, Past Medical History, Doctor's Observations, Preliminary Assessment, Next Steps, Referral Details, Subtext Analysis, Patient Details, Hospital/Doctor Details, Clinical Information |
| **JSON** | 3 | Prescription Data, Treatment Plan, Protocol |

### Critical Segments for Requirements

**Subtext Analysis** [FORMATTED]:
```
Patient Factors:
  Anxiety Level (Before): Moderate
  Anxiety Level (After): Low
  Financial Considerations: Can afford treatment
  Compliance Likelihood: High

Doctor Factors:
  Communication Style: Reassuring
```

**Patient Details** [FORMATTED]:
```
Name: Ram Kumar
Age: 45 years
Gender: Male
Height: 170 cm
Weight: 75 kg
```

**Prescription Data** [JSON]:
```json
[
  {
    "Medicine Name": "Amlodipine 5mg",
    "Morning": "1",
    "Noon": "0",
    "Evening": "0",
    "Night": "0",
    "Duration (Days)": "30",
    "Time to Take": "Before food",
    "Remarks": "Monitor blood pressure"
  }
]
```

---

## Enhanced Database Schema

### Table 1: `record_segments` ⭐ NEW

**Purpose:** Store all 26 segments from Pradhi with edit tracking

```sql
CREATE TABLE IF NOT EXISTS record_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL,
    segment_type VARCHAR(100) NOT NULL,
    storage_format VARCHAR(20) NOT NULL,  -- 'TEXT', 'FORMATTED', 'JSON'

    original_content TEXT NOT NULL,
    edited_content TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    edited_at TIMESTAMP WITH TIME ZONE,
    edited_by UUID,  -- FK to experts (for isolation)

    CONSTRAINT fk_consultation FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE,
    CONSTRAINT fk_edited_by FOREIGN KEY (edited_by)
        REFERENCES experts (id)
);

CREATE INDEX idx_segments_consultation ON record_segments (consultation_id);
CREATE INDEX idx_segments_type ON record_segments (segment_type);
CREATE INDEX idx_segments_edited ON record_segments (edited_at) WHERE edited_content IS NOT NULL;
CREATE INDEX idx_segments_expert ON record_segments (edited_by);  -- ⭐ For expert isolation
```

**Key Features:**
- Source of truth for all medical record segments
- Preserves original AI-generated content
- Tracks doctor edits separately with `edited_by` for expert attribution
- Enables expert-scoped adaptive learning

---

### Table 2: `consultations` (ENHANCED)

**Purpose:** Aggregated structured view with rich extracted fields

```sql
CREATE TABLE IF NOT EXISTS consultations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id TEXT NOT NULL UNIQUE,
    client_id UUID NOT NULL,
    org_client_id INT NOT NULL,
    expert_id UUID NOT NULL,
    org_id UUID NOT NULL,

    -- DEMOGRAPHICS
    patient_name TEXT,
    patient_age INT,
    patient_dob DATE,
    patient_gender TEXT,
    patient_height TEXT,
    patient_weight TEXT,

    -- TEMPORAL
    consultation_date TIMESTAMP WITH TIME ZONE,
    start_date DATE,

    -- CLINICAL
    chief_complaint TEXT,
    associated_symptoms TEXT[],
    diagnosis TEXT,
    icd_10_code TEXT,
    severity_assessment TEXT,

    -- VITALS & OBSERVATIONS
    vitals JSONB,
    physical_examination TEXT,

    -- HISTORY
    past_diagnosis TEXT,
    allergies TEXT,
    family_history TEXT,

    -- TREATMENT
    medications JSONB,
    treatment_plan JSONB,
    protocol JSONB,
    prescriptions JSONB,

    -- PSYCHOSOCIAL ⭐ NEW
    anxiety_level_before TEXT,
    anxiety_level_after TEXT,
    financial_considerations TEXT,
    compliance_likelihood TEXT,
    patient_engagement_level TEXT,
    doctor_communication_style TEXT,

    -- ADMINISTRATIVE
    referral_specialist TEXT,
    referral_reason TEXT,
    next_steps TEXT,

    -- RAW DATA
    full_segments_data JSONB,

    -- METADATA
    created_time TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_client FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE,
    CONSTRAINT fk_expert FOREIGN KEY (expert_id) REFERENCES experts (id),
    CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES organizations (id)
);

-- Composite query indexes
CREATE INDEX idx_consultations_client_date ON consultations (client_id, consultation_date DESC);
CREATE INDEX idx_consultations_org_client ON consultations (org_client_id, org_id);
CREATE INDEX idx_consultations_expert_date ON consultations (expert_id, consultation_date DESC);  -- ⭐ For expert queries
CREATE INDEX idx_consultations_date_range ON consultations (consultation_date);
CREATE INDEX idx_consultations_diagnosis ON consultations USING GIN (to_tsvector('english', diagnosis));

-- Analytics indexes ⭐ NEW
CREATE INDEX idx_consultations_anxiety ON consultations (anxiety_level_before, anxiety_level_after)
    WHERE anxiety_level_before IS NOT NULL;
CREATE INDEX idx_consultations_compliance ON consultations (compliance_likelihood);

-- Data validation constraints ⭐ NEW (v2.2)
ALTER TABLE consultations ADD CONSTRAINT check_anxiety_level_before
    CHECK (anxiety_level_before IN ('High', 'Moderate', 'Low') OR anxiety_level_before IS NULL);

ALTER TABLE consultations ADD CONSTRAINT check_anxiety_level_after
    CHECK (anxiety_level_after IN ('High', 'Moderate', 'Low') OR anxiety_level_after IS NULL);

ALTER TABLE consultations ADD CONSTRAINT check_patient_gender
    CHECK (patient_gender IN ('Male', 'Female', 'Other', 'Prefer not to say') OR patient_gender IS NULL);

ALTER TABLE consultations ADD CONSTRAINT check_compliance_likelihood
    CHECK (compliance_likelihood IN ('High', 'Moderate', 'Low') OR compliance_likelihood IS NULL);

-- ICD-10 code format validation (optional - can be disabled for performance)
-- Format: Letter followed by 2 digits, optionally followed by decimal and 1-4 digits
-- Examples: A00, J45.9, E11.65
ALTER TABLE consultations ADD CONSTRAINT check_icd_10_format
    CHECK (icd_10_code IS NULL OR icd_10_code ~ '^[A-Z][0-9]{2}(\.[0-9]{1,4})?$');

-- NOT NULL constraints on critical fields
ALTER TABLE consultations ALTER COLUMN consultation_date SET NOT NULL;
ALTER TABLE consultations ALTER COLUMN expert_id SET NOT NULL;
```

---

### Table 3: `consultation_edits` ⭐ NEW (Expert-Scoped)

**Purpose:** Track edits for **expert-specific** adaptive learning

```sql
CREATE TABLE IF NOT EXISTS consultation_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL,
    segment_type VARCHAR(100) NOT NULL,
    field_name VARCHAR(100),

    original_value TEXT NOT NULL,
    edited_value TEXT NOT NULL,

    -- Diff analysis for adaptive learning
    word_diff JSONB,
    char_diff_count INT,
    edit_type VARCHAR(50),  -- 'correction', 'addition', 'removal', 'rephrasing'

    -- Metadata
    edit_reason TEXT,
    edited_by UUID NOT NULL,  -- ⭐ CRITICAL: Expert who made the edit
    edited_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Adaptive learning flags
    pattern_analyzed BOOLEAN DEFAULT FALSE,
    feedback_incorporated BOOLEAN DEFAULT FALSE,

    CONSTRAINT fk_consultation_edit FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE,
    CONSTRAINT fk_editor FOREIGN KEY (edited_by) REFERENCES experts (id)
);

CREATE INDEX idx_edits_consultation ON consultation_edits (consultation_id);
CREATE INDEX idx_edits_segment_type ON consultation_edits (segment_type);
CREATE INDEX idx_edits_expert ON consultation_edits (edited_by);  -- ⭐ Expert isolation
CREATE INDEX idx_edits_expert_segment ON consultation_edits (edited_by, segment_type);  -- ⭐ Pattern queries
CREATE INDEX idx_edits_analyzed ON consultation_edits (pattern_analyzed) WHERE NOT pattern_analyzed;

-- Row-level security for expert privacy
ALTER TABLE consultation_edits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Experts can only view own edits"
ON consultation_edits
FOR SELECT
USING (edited_by = auth.uid()::uuid);
```

---

### Table 4: `edit_patterns` ⭐ NEW (Expert-Scoped Learning)

**Purpose:** Store learned patterns **per expert** for adaptive learning

```sql
CREATE TABLE IF NOT EXISTS edit_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id UUID NOT NULL,  -- ⭐ SCOPED PER EXPERT
    segment_type VARCHAR(100) NOT NULL,

    -- Pattern data specific to THIS EXPERT
    patterns JSONB NOT NULL,
    /* Example structure:
    {
      "common_corrections": {
        "hypertention": "hypertension",  // This expert's common typos
        "diabetis": "diabetes",
        "febver": "fever"
      },
      "terminology_preferences": {
        "high blood pressure": "hypertension",  // Prefers medical terms
        "sugar": "diabetes mellitus",
        "heart attack": "myocardial infarction"
      },
      "style_preferences": {
        "tone": "formal",  // vs "conversational"
        "detail_level": "comprehensive",  // vs "concise"
        "structure": "symptom-first",  // vs "diagnosis-first"
        "preferred_phrases": [
          "presents with",
          "reports experiencing",
          "denies any"
        ]
      },
      "structural_improvements": {
        "add_timeline": true,  // Always adds timeline to symptoms
        "include_negatives": true,  // Includes what patient denies
        "measurement_units": "metric"  // vs "imperial"
      }
    }
    */

    -- Metadata
    sample_count INT,  -- How many edits analyzed for this pattern
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confidence_score FLOAT,  -- 0.0 to 1.0, how confident we are

    CONSTRAINT fk_expert_patterns FOREIGN KEY (expert_id)
        REFERENCES experts (id) ON DELETE CASCADE,
    CONSTRAINT unique_expert_segment_pattern UNIQUE (expert_id, segment_type)
);

CREATE INDEX idx_edit_patterns_expert ON edit_patterns (expert_id);
CREATE INDEX idx_edit_patterns_segment ON edit_patterns (segment_type);
CREATE INDEX idx_edit_patterns_confidence ON edit_patterns (confidence_score) WHERE confidence_score > 0.7;

-- Row-level security for expert privacy
ALTER TABLE edit_patterns ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Experts can only view own patterns"
ON edit_patterns
FOR SELECT
USING (expert_id = auth.uid()::uuid);
```

**Key Features:**
- **Completely isolated per expert** - Dr. Smith's patterns never affect Dr. Jones
- Stores expert-specific correction patterns, terminology preferences, and style
- Confidence scoring based on sample size
- Privacy-preserving with row-level security

---

### Table 5: `ehr_export_configs` ⭐ NEW

**Purpose:** Configurable field mappings for EHR export

```sql
CREATE TABLE IF NOT EXISTS ehr_export_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    specialty VARCHAR(100),
    export_format VARCHAR(50) NOT NULL,

    field_mappings JSONB NOT NULL,
    export_rules JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX idx_export_config_specialty ON ehr_export_configs (specialty);
CREATE INDEX idx_export_config_format ON ehr_export_configs (export_format);
```

---

### Table 6: `record_merge_configs` ⭐ NEW

**Purpose:** Define merging strategies

```sql
CREATE TABLE IF NOT EXISTS record_merge_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    merge_strategy VARCHAR(50) NOT NULL,

    grouping_criteria JSONB NOT NULL,
    merge_rules JSONB NOT NULL,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_merge_config_strategy ON record_merge_configs (merge_strategy);
```

---

### Table 7: `merged_records` ⭐ NEW

**Purpose:** Materialized merged views

```sql
CREATE TABLE IF NOT EXISTS merged_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merged_record_id TEXT NOT NULL UNIQUE,
    config_name VARCHAR(100) NOT NULL,

    org_client_id INT NOT NULL,
    patient_id UUID,

    source_consultation_ids UUID[] NOT NULL,
    consultation_count INT NOT NULL,
    date_range_start TIMESTAMP WITH TIME ZONE,
    date_range_end TIMESTAMP WITH TIME ZONE,

    merged_data JSONB NOT NULL,
    summary TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_regenerated_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT fk_merge_config FOREIGN KEY (config_name)
        REFERENCES record_merge_configs (config_name)
);

CREATE INDEX idx_merged_records_patient ON merged_records (org_client_id);
CREATE INDEX idx_merged_records_config ON merged_records (config_name);
CREATE INDEX idx_merged_records_expires ON merged_records (expires_at);
```

---

### Table 8: `segment_type_mappings` ⭐ NEW (v2.2)

**Purpose:** Normalize Pradhi segment names to internal names for consistency

```sql
CREATE TABLE IF NOT EXISTS segment_type_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pradhi_name VARCHAR(100) NOT NULL UNIQUE,
    internal_name VARCHAR(100) NOT NULL UNIQUE,
    storage_format VARCHAR(20) NOT NULL,  -- 'TEXT', 'FORMATTED', 'JSON'
    description TEXT,
    extraction_priority INT DEFAULT 0,  -- Higher = more critical for extraction
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT check_storage_format CHECK (storage_format IN ('TEXT', 'FORMATTED', 'JSON'))
);

CREATE INDEX idx_segment_mappings_pradhi ON segment_type_mappings (pradhi_name);
CREATE INDEX idx_segment_mappings_internal ON segment_type_mappings (internal_name);
CREATE INDEX idx_segment_mappings_format ON segment_type_mappings (storage_format);

-- Seed data for all 26 Pradhi segments
INSERT INTO segment_type_mappings (pradhi_name, internal_name, storage_format, description, extraction_priority) VALUES
    -- TEXT format segments (15 total)
    ('Summary', 'Summary', 'TEXT', 'Overall consultation summary', 10),
    ('Analysis', 'Analysis', 'TEXT', 'Clinical analysis', 9),
    ('Key Facts', 'KeyFacts', 'TEXT', 'Important consultation facts', 8),
    ('Timestamped Transcription', 'TimestampedTranscription', 'TEXT', 'Full consultation transcript', 5),
    ('Chief Complaint(s)', 'ChiefComplaint', 'TEXT', 'Primary patient complaints', 10),
    ('Associated Symptoms', 'AssociatedSymptoms', 'TEXT', 'Symptoms associated with chief complaint', 9),
    ('Diagnosis', 'Diagnosis', 'TEXT', 'Medical diagnosis', 10),
    ('Additional Observations', 'AdditionalObservations', 'TEXT', 'Extra clinical observations', 6),
    ('Start Date', 'StartDate', 'TEXT', 'Symptom or condition start date', 7),
    ('Context', 'Context', 'TEXT', 'Additional context', 5),
    ('Investigation', 'Investigation', 'TEXT', 'Ordered tests and investigations', 8),
    ('History', 'History', 'TEXT', 'Patient medical history', 9),
    ('Examination', 'Examination', 'TEXT', 'Physical examination findings', 8),
    ('Timeline', 'Timeline', 'TEXT', 'Chronological progression of symptoms', 7),
    ('Follow-up', 'FollowUp', 'TEXT', 'Follow-up instructions', 7),

    -- FORMATTED segments (11 total)
    ('Present Illness Information', 'PresentIllnessInfo', 'FORMATTED', 'Details of current illness', 8),
    ('Past Medical History', 'PastMedicalHistory', 'FORMATTED', 'Previous medical conditions', 7),
    ('Doctor''s Observations', 'DoctorObservations', 'FORMATTED', 'Physician observations', 7),
    ('Preliminary Assessment', 'PreliminaryAssessment', 'FORMATTED', 'Initial clinical assessment', 8),
    ('Next Steps', 'NextSteps', 'FORMATTED', 'Treatment next steps', 8),
    ('Referral Details', 'ReferralDetails', 'FORMATTED', 'Specialist referral information', 6),
    ('Subtext Analysis', 'SubtextAnalysis', 'FORMATTED', 'Psychosocial factors (anxiety, compliance, financial)', 10),
    ('Patient Details', 'PatientDetails', 'FORMATTED', 'Demographics (name, age, DOB, gender, vitals)', 10),
    ('Hospital/Doctor Details', 'HospitalDoctorDetails', 'FORMATTED', 'Provider information', 5),
    ('Clinical Information', 'ClinicalInformation', 'FORMATTED', 'General clinical data', 7),
    ('Vitals', 'Vitals', 'FORMATTED', 'Vital signs measurements', 8),

    -- JSON segments (3 total)
    ('Prescription Data', 'PrescriptionData', 'JSON', 'Structured medication data', 10),
    ('Treatment Plan', 'TreatmentPlan', 'JSON', 'Structured treatment plan', 9),
    ('Protocol', 'Protocol', 'JSON', 'Clinical protocol information', 6)
ON CONFLICT (pradhi_name) DO NOTHING;
```

**Key Features:**
- **Normalization:** Maps Pradhi segment names (with special characters) to clean internal names
- **Storage format tracking:** Enables format-specific parsing logic
- **Extraction priority:** Guides which fields to extract first (10 = highest priority)
- **Extensibility:** New segments can be added without code changes

**Usage Example:**
```python
async def normalize_segment_type(pradhi_name: str) -> str:
    """Convert Pradhi segment name to internal name"""
    mapping = await supabase.table("segment_type_mappings").select(
        "internal_name, storage_format"
    ).eq("pradhi_name", pradhi_name).execute()

    if mapping.data:
        return mapping.data[0]

    # Fallback: Strip special chars and spaces
    return pradhi_name.replace("(", "").replace(")", "").replace(" ", "").replace("/", "")
```

---

## Vector Store Strategy - Three-Tier System

### Tier 1: Per-Segment Files (Highest Precision)

**Naming:** `consultation_{consultation_id}_segment_{segment_type}_{org/expert_id}.json`

**Examples:**
- `consultation_CONS001_segment_ChiefComplaint_org123.json`
- `consultation_CONS001_segment_SubtextAnalysis_expert456.json`
- `consultation_CONS001_segment_PrescriptionData_org123.json`

**Content Structure:**
```json
{
  "consultation_id": "CONS001",
  "segment_type": "Chief Complaint(s)",
  "storage_format": "TEXT",
  "patient_context": {
    "org_client_id": 12345,
    "name": "Ram Kumar",
    "age": 45,
    "gender": "Male"
  },
  "segment_content": "Headaches\nFatigue\nDizziness",
  "metadata": {
    "consultation_date": "2025-10-18T10:30:00Z",
    "expert_name": "Dr. Smith",
    "expert_id": "expert456"
  }
}
```

**Benefit:** Ultra-precise RAG - LLM only processes 1 segment instead of entire consultation

### Tier 2: Aggregated Consultation Files

**Naming:** `consultation_{consultation_id}_summary_{org/expert_id}.json`

**Content:** All extracted structured fields + key segments combined

### Tier 3: Merged Record Files

**Naming:** `patient_{org_client_id}_merged_{config_name}_{org_id}.json`

**Content:** Merged data from multiple consultations

**Benefit:** Longitudinal patient view for historical queries

---

## Vector Store Organization & Scaling Strategy ⭐ NEW (v2.2)

### The Scaling Challenge

**Problem:** OpenAI vector stores have a **10,000 file limit per vector store**.

**Math:**
- 26 segments per consultation
- 100 consultations/day per expert
- Daily files: 26 × 100 = 2,600 files
- Files to hit limit: 10,000 ÷ 2,600 = ~3.8 days ❌

**This breaks in less than a week!**

### Solution: Monthly Vector Store Rollover

**Strategy: One vector store per expert per month**

```python
def get_expert_vector_store_id(expert_id: UUID, consultation_date: datetime) -> str:
    """Get or create monthly vector store for expert"""
    year_month = consultation_date.strftime("%Y_%m")
    vector_store_name = f"{expert_id}_{year_month}"

    # Check if exists
    existing = await supabase.table("vector_stores").select("*").eq(
        "vector_name", vector_store_name
    ).execute()

    if existing.data:
        return existing.data[0]["vector_id"]

    # Create new monthly vector store
    vector_store = client.vector_stores.create(name=vector_store_name)

    await supabase.table("vector_stores").insert({
        "vector_id": vector_store.id,
        "vector_name": vector_store_name,
        "expert_id": expert_id,
        "owner": "expert",
        "org_id": expert.org_id,
        "created_at": datetime.now()
    }).execute()

    return vector_store.id
```

**Benefits:**
- Each expert's monthly vector store: max 2,600 × 30 = 78,000 files (well under 10K limit per day, ~7.8K per month)
- Automatic archival (delete vector stores older than 2 years)
- Query optimization (recent consultations in current month's store)

### Vector Store File Organization

**Per Expert:**
- `{expert_id}_2025_10` - October 2025 consultations (current)
- `{expert_id}_2025_09` - September 2025 consultations (archived)
- `{expert_id}_2025_08` - August 2025 consultations (archived)

**Per Client (Org-level):**
- `client_{org_client_id}_2025_10` - All consultations for this patient in October
- `client_{org_client_id}_2025_09` - September consultations

**Query Strategy:**
```python
async def query_with_timeframe(expert_id: UUID, query: str, months_back: int = 3):
    """Query across multiple monthly vector stores"""
    current_month = datetime.now()
    vector_store_ids = []

    for i in range(months_back):
        month = current_month - timedelta(days=30*i)
        vector_store_name = f"{expert_id}_{month.strftime('%Y_%m')}"

        store = await supabase.table("vector_stores").select("vector_id").eq(
            "vector_name", vector_store_name
        ).execute()

        if store.data:
            vector_store_ids.append(store.data[0]["vector_id"])

    # Query across multiple vector stores
    assistant = await get_or_create_assistant(
        expert_id=expert_id,
        vector_store_ids=vector_store_ids  # Multiple stores!
    )
    # ... rest of query logic
```

### Storage Cost Estimation ⭐ NEW (v2.2)

**Per Consultation:**
- 26 segment files × 5 KB average = 130 KB
- Supabase JSONB storage: ~130 KB
- OpenAI vector storage: ~130 KB

**Monthly Costs (100 consultations/day per expert):**
- Total consultations: 100 × 30 = 3,000/month
- Total files: 3,000 × 26 = 78,000 files
- Total storage: 78,000 × 5 KB = 390 MB
- **OpenAI cost:** $0.10/GB/month = 0.39 GB × $0.10 = **$0.039/month/expert**
- **Supabase cost:** Included in free tier (up to 500MB)

**Annual Costs:**
- Per expert: $0.039 × 12 = **$0.47/year**
- 100 experts: $0.47 × 100 = **$47/year total**
- 1,000 experts: **$470/year total**

**Conclusion: Storage costs are negligible** ✅

### Archive & Cleanup Strategy

```python
async def archive_old_vector_stores(retention_months: int = 24):
    """Delete vector stores older than retention period"""
    cutoff_date = datetime.now() - timedelta(days=30 * retention_months)

    old_stores = await supabase.table("vector_stores").select("*").lt(
        "created_at", cutoff_date
    ).eq("owner", "expert").execute()

    for store in old_stores.data:
        # Delete from OpenAI
        client.vector_stores.delete(store["vector_id"])

        # Mark as archived in database
        await supabase.table("vector_stores").update({
            "archived_at": datetime.now(),
            "status": "archived"
        }).eq("id", store["id"]).execute()

    return len(old_stores.data)
```

**Retention Policy:**
- Active consultations: Current month + 23 previous months (2 years)
- Archived consultations: Remain in Supabase `consultations` table indefinitely
- Vector stores deleted after 2 years (can be regenerated from database if needed)

---

## Expert-Scoped Adaptive Learning Implementation

### 1. Webhook Processing ⭐ CORRECTED (v2.2)

**🔴 CRITICAL FIX:** Previous version applied patterns BEFORE storage, creating circular logic!
**✅ NEW APPROACH:** Store pristine originals, apply patterns for UI display only.

```python
async def process_pradhi_webhook(webhook_data: dict):
    """
    Process incoming Pradhi webhook with all 26 segments

    CRITICAL: Stores PRISTINE original content from Pradhi.
    Patterns are applied later for UI display, NOT for storage!
    """
    consultation_id = webhook_data["consultation_id"]
    org_client_id = webhook_data["org_client_id"]
    expert_id = webhook_data["expert_id"]
    org_id = webhook_data["org_id"]

    segments = webhook_data["segments"]  # Array of 26 segment objects (pristine from Pradhi)

    # Step 1: Store PRISTINE ORIGINAL segments (NO pattern application)
    # This preserves the true AI-generated content for adaptive learning
    consultation_uuid = str(uuid.uuid4())

    for segment in segments:
        # Normalize segment type from Pradhi name to internal name
        normalized_type = await normalize_segment_type(segment["type"])

        await supabase.table("record_segments").insert({
            "consultation_id": consultation_uuid,
            "segment_type": normalized_type,
            "storage_format": segment["format"],
            "original_content": segment["content"],  # ⭐ PRISTINE from Pradhi
            "edited_content": None,  # No edits yet
            "edited_by": None
        }).execute()

    # Step 2: Extract structured fields from ORIGINAL content
    extracted_fields = await extract_all_fields(segments)

    # Step 3: Create consultation record with original data
    await supabase.table("consultations").insert({
        "consultation_id": consultation_id,
        "id": consultation_uuid,
        "client_id": await get_or_create_client(org_client_id),
        "org_client_id": org_client_id,
        "expert_id": expert_id,
        "org_id": org_id,
        **extracted_fields,
        "full_segments_data": {seg["type"]: seg["content"] for seg in segments}
    }).execute()

    # Step 4: Create vector store files with ORIGINAL content
    vector_store_id = await get_expert_vector_store_id(
        expert_id,
        extracted_fields.get("consultation_date", datetime.now())
    )

    await create_vector_files_for_consultation(
        consultation_id=consultation_uuid,
        segments=segments,  # Original segments
        extracted_fields=extracted_fields,
        vector_store_id=vector_store_id
    )

    # Step 5: Generate SUGGESTED edits for UI (patterns applied here)
    suggested_segments = []
    for segment in segments:
        normalized_type = await normalize_segment_type(segment["type"])

        # Apply THIS expert's learned patterns to generate suggestions
        suggested_content = await apply_expert_learned_patterns(
            expert_id=expert_id,
            segment_type=normalized_type,
            ai_generated_content=segment["content"]  # Original content
        )

        suggested_segments.append({
            **segment,
            "original_content": segment["content"],  # Pristine
            "suggested_content": suggested_content,  # With patterns applied
            "has_suggestions": suggested_content != segment["content"]
        })

    # Step 6: Return to UI with BOTH original and suggested content
    return {
        "consultation_id": consultation_id,
        "consultation_uuid": consultation_uuid,
        "status": "success",
        "segments": suggested_segments,  # UI can show suggestions alongside originals
        "message": "Consultation stored. Review suggested edits before publishing."
    }
```

**Key Changes:**
1. **Storage:** Always stores pristine original from Pradhi
2. **Pattern Application:** Only for UI suggestions, not database storage
3. **Expert Review:** Expert sees suggested content, can accept/modify/reject
4. **Edit Tracking:** Compares expert's final edit vs. original (true learning)
5. **Rollback:** Original always preserved for audit and reprocessing

**UI Workflow:**
```javascript
// Frontend receives suggested_segments
{
  "segments": [
    {
      "type": "Diagnosis",
      "original_content": "Patient has diabetis and hypertention",
      "suggested_content": "Patient has diabetes and hypertension",  // Pattern-corrected
      "has_suggestions": true
    }
  ]
}

// Expert can:
// 1. Accept suggestion → saves suggested_content as edited_content
// 2. Modify suggestion → saves custom edit as edited_content
// 3. Reject suggestion → keeps original_content (no edit record)
```

### 2. Expert-Specific Pattern Application

```python
async def apply_expert_learned_patterns(
    expert_id: UUID,
    segment_type: str,
    ai_generated_content: str
) -> str:
    """
    Apply THIS EXPERT's learned patterns to new AI-generated content

    When Pradhi generates a consultation, BEFORE showing to the expert,
    apply their personal learned patterns for pre-correction

    ⭐ CRITICAL: Only uses patterns from THIS expert, never from others
    """
    # Get THIS expert's patterns for this segment type
    patterns = await supabase.table("edit_patterns").select("*").eq(
        "expert_id", expert_id  # ⭐ EXPERT ISOLATION
    ).eq("segment_type", segment_type).execute()

    if not patterns.data:
        return ai_generated_content  # No patterns yet, return as-is

    expert_patterns = patterns.data[0]["patterns"]
    confidence = patterns.data[0]["confidence_score"]

    # Only apply if confidence is high enough (minimum 70%)
    if confidence < 0.7:
        return ai_generated_content

    modified_content = ai_generated_content

    # Apply common corrections (typo fixes this expert always makes)
    for incorrect, correct in expert_patterns.get("common_corrections", {}).items():
        modified_content = modified_content.replace(incorrect, correct)

    # Apply terminology preferences (this expert's preferred medical terms)
    for informal, formal in expert_patterns.get("terminology_preferences", {}).items():
        # Use word boundary matching to avoid partial replacements
        import re
        pattern = r'\b' + re.escape(informal) + r'\b'
        modified_content = re.sub(pattern, formal, modified_content, flags=re.IGNORECASE)

    # Apply style preferences
    style = expert_patterns.get("style_preferences", {})
    if style.get("tone") == "formal":
        modified_content = apply_formal_tone(modified_content)

    # Apply structural improvements
    structural = expert_patterns.get("structural_improvements", {})
    if structural.get("measurement_units") == "metric":
        modified_content = convert_to_metric(modified_content)

    return modified_content
```

### 3. Edit Tracking (Expert-Scoped)

```python
async def track_edit(
    consultation_id: UUID,
    segment_type: str,
    original_content: str,
    edited_content: str,
    edited_by: UUID,  # ⭐ Expert who made the edit
    edit_reason: str = None
):
    """
    Track edit and perform diff analysis for THIS expert's adaptive learning
    """
    import difflib

    # Compute word-level diff
    original_words = original_content.split()
    edited_words = edited_content.split()

    diff = list(difflib.unified_diff(
        original_words,
        edited_words,
        lineterm=''
    ))

    # Analyze edit type
    additions = [line for line in diff if line.startswith('+')]
    removals = [line for line in diff if line.startswith('-')]

    if len(additions) > len(removals):
        edit_type = "addition"
    elif len(removals) > len(additions):
        edit_type = "removal"
    elif len(additions) == len(removals) and additions:
        edit_type = "correction"
    else:
        edit_type = "rephrasing"

    # Store edit with expert attribution
    await supabase.table("consultation_edits").insert({
        "consultation_id": consultation_id,
        "segment_type": segment_type,
        "original_value": original_content,
        "edited_value": edited_content,
        "word_diff": diff,
        "char_diff_count": len(edited_content) - len(original_content),
        "edit_type": edit_type,
        "edit_reason": edit_reason,
        "edited_by": edited_by  # ⭐ Expert attribution
    }).execute()

    # Update record_segments
    await supabase.table("record_segments").update({
        "edited_content": edited_content,
        "edited_at": datetime.now(),
        "edited_by": edited_by
    }).eq("consultation_id", consultation_id).eq(
        "segment_type", segment_type
    ).execute()

    # Update extracted field in consultations table if needed
    await update_extracted_field_if_applicable(
        consultation_id,
        segment_type,
        edited_content
    )

    # Update vector store files
    await update_vector_files_with_edit(
        consultation_id,
        segment_type,
        edited_content
    )

    # Trigger expert-specific adaptive learning analysis (async)
    asyncio.create_task(
        analyze_expert_edit_pattern_async(
            expert_id=edited_by,  # ⭐ Pass expert ID
            segment_type=segment_type
        )
    )
```

### 4. Expert-Specific Pattern Analysis

```python
async def analyze_expert_edit_pattern_async(expert_id: UUID, segment_type: str):
    """
    Background task for EXPERT-SPECIFIC adaptive learning analysis

    ⭐ CRITICAL: Only analyzes edits from THIS expert, never from others
    """
    # ⭐ ONLY get edits from THIS EXPERT for this segment type
    expert_edits = await supabase.table("consultation_edits").select("*").eq(
        "segment_type", segment_type
    ).eq("edited_by", expert_id).eq(  # ⭐ KEY ISOLATION
        "pattern_analyzed", False
    ).limit(100).execute()

    if len(expert_edits.data) < 5:  # Need minimum edits per expert
        return  # Not enough data yet for this expert

    # Analyze patterns ONLY from this expert's edits
    patterns = {
        "common_corrections": extract_common_corrections(expert_edits.data),
        "terminology_preferences": extract_terminology_preferences(expert_edits.data),
        "style_preferences": extract_style_preferences(expert_edits.data),
        "structural_improvements": extract_structural_changes(expert_edits.data)
    }

    # Calculate confidence based on sample size and consistency
    confidence_score = calculate_confidence(
        sample_count=len(expert_edits.data),
        pattern_consistency=calculate_pattern_consistency(expert_edits.data)
    )

    # Store patterns SCOPED TO THIS EXPERT
    await supabase.table("edit_patterns").upsert({
        "expert_id": expert_id,  # ⭐ EXPERT-SPECIFIC
        "segment_type": segment_type,
        "patterns": patterns,
        "sample_count": len(expert_edits.data),
        "confidence_score": confidence_score,
        "last_updated": datetime.now()
    }).execute()

    # Mark ONLY this expert's edits as analyzed
    for edit in expert_edits.data:
        await supabase.table("consultation_edits").update({
            "pattern_analyzed": True
        }).eq("id", edit["id"]).execute()

    # Generate feedback report for THIS EXPERT ONLY
    await generate_expert_specific_learning_report(expert_id, segment_type, patterns)

def extract_common_corrections(edits: list) -> dict:
    """
    Extract common word replacements this expert makes
    """
    corrections = {}
    for edit in edits:
        original_words = set(edit["original_value"].split())
        edited_words = set(edit["edited_value"].split())

        # Find words that were replaced
        removed = original_words - edited_words
        added = edited_words - original_words

        # Simple heuristic: if removed and added have same count, likely corrections
        if len(removed) == len(added):
            for old, new in zip(sorted(removed), sorted(added)):
                if old not in corrections:
                    corrections[old] = {}
                corrections[old][new] = corrections[old].get(new, 0) + 1

    # Keep only high-frequency corrections (appears 3+ times)
    frequent_corrections = {}
    for old_word, replacements in corrections.items():
        most_common = max(replacements, key=replacements.get)
        if replacements[most_common] >= 3:
            frequent_corrections[old_word] = most_common

    return frequent_corrections

def calculate_confidence(sample_count: int, pattern_consistency: float) -> float:
    """
    Calculate confidence score (0.0 to 1.0) based on data quality
    """
    # Base confidence on sample size
    if sample_count < 5:
        size_score = 0.3
    elif sample_count < 10:
        size_score = 0.5
    elif sample_count < 20:
        size_score = 0.7
    else:
        size_score = 0.9

    # Combine with pattern consistency
    return (size_score * 0.6) + (pattern_consistency * 0.4)
```

### 5. Expert-Specific Learning Dashboard

```python
@router.get("/experts/{expert_id}/learning-stats")
async def get_expert_learning_stats(expert_id: UUID):
    """
    Show THIS expert their personalized learning statistics

    - How many edits they've made
    - What patterns have been learned
    - Confidence scores per segment
    - Improvement metrics over time
    """
    # Get edit count per segment for this expert
    edits_by_segment = await supabase.table("consultation_edits").select(
        "segment_type"
    ).eq("edited_by", expert_id).execute()

    segment_counts = {}
    for edit in edits_by_segment.data:
        seg_type = edit["segment_type"]
        segment_counts[seg_type] = segment_counts.get(seg_type, 0) + 1

    # Get learned patterns for this expert
    patterns = await supabase.table("edit_patterns").select("*").eq(
        "expert_id", expert_id
    ).execute()

    # Calculate accuracy improvement (edits decreasing over time = AI learning)
    recent_edits = await supabase.table("consultation_edits").select("*").eq(
        "edited_by", expert_id
    ).gte("edited_at", datetime.now() - timedelta(days=30)).execute()

    older_edits = await supabase.table("consultation_edits").select("*").eq(
        "edited_by", expert_id
    ).lt("edited_at", datetime.now() - timedelta(days=30)).gte(
        "edited_at", datetime.now() - timedelta(days=60)
    ).execute()

    recent_count = len(recent_edits.data)
    older_count = len(older_edits.data)

    if older_count > 0:
        improvement_rate = ((older_count - recent_count) / older_count) * 100
    else:
        improvement_rate = 0

    return {
        "expert_id": expert_id,
        "total_edits": sum(segment_counts.values()),
        "edits_by_segment": segment_counts,
        "segments_with_learned_patterns": len(patterns.data),
        "patterns": [
            {
                "segment_type": p["segment_type"],
                "confidence": p["confidence_score"],
                "sample_count": p["sample_count"],
                "last_updated": p["last_updated"],
                "top_corrections": list(p["patterns"].get("common_corrections", {}).items())[:5],
                "terminology_preferences": list(p["patterns"].get("terminology_preferences", {}).items())[:3]
            }
            for p in patterns.data
        ],
        "improvement_metrics": {
            "recent_edits_30_days": recent_count,
            "older_edits_30_60_days": older_count,
            "improvement_rate_percent": round(improvement_rate, 1),
            "ai_learning_status": "improving" if improvement_rate > 10 else "stable"
        },
        "effectiveness_score": calculate_effectiveness(patterns.data)
    }

def calculate_effectiveness(patterns: list) -> float:
    """
    Calculate overall effectiveness of adaptive learning for this expert
    """
    if not patterns:
        return 0.0

    avg_confidence = sum(p["confidence_score"] for p in patterns) / len(patterns)
    total_samples = sum(p["sample_count"] for p in patterns)

    # Effectiveness based on confidence and sample size
    if total_samples > 50 and avg_confidence > 0.8:
        return 0.95
    elif total_samples > 30 and avg_confidence > 0.7:
        return 0.80
    elif total_samples > 15 and avg_confidence > 0.6:
        return 0.65
    else:
        return 0.40
```

---

## Vector File Update Mechanism ⭐ NEW (v2.2)

**Problem:** When an expert edits a segment, the corresponding vector file must be updated.
**Challenge:** OpenAI doesn't support in-place file updates.
**Solution:** Delete old file, create new file with edited content.

```python
async def update_vector_files_with_edit(
    consultation_id: UUID,
    segment_type: str,
    edited_content: str
):
    """
    Update vector store file when segment is edited

    Strategy: DELETE-AND-RECREATE (OpenAI limitation)
    1. Find existing file
    2. Create new file with edited content
    3. Remove old file from vector store
    4. Add new file to vector store
    5. Delete old file from OpenAI (cleanup)
    """
    # 1. Find consultation record to get vector store ID
    consultation = await supabase.table("consultations").select(
        "expert_id, consultation_date"
    ).eq("id", consultation_id).execute()

    if not consultation.data:
        raise HTTPException(404, "Consultation not found")

    expert_id = consultation.data[0]["expert_id"]
    consultation_date = consultation.data[0]["consultation_date"]

    # Get expert's monthly vector store
    vector_store_id = await get_expert_vector_store_id(expert_id, consultation_date)

    # 2. Find existing file in documents table
    file_name = f"consultation_{consultation_id}_segment_{segment_type}"

    file_query = await supabase.table("documents").select("*").eq(
        "name", file_name
    ).eq("owner_id", str(expert_id)).execute()

    old_file_id = None
    if file_query.data:
        old_file_id = file_query.data[0]["openai_file_id"]

    # 3. Create NEW file with edited content
    # Get full segment context for better RAG
    segment_record = await supabase.table("record_segments").select("*").eq(
        "consultation_id", consultation_id
    ).eq("segment_type", segment_type).execute()

    if not segment_record.data:
        raise HTTPException(404, "Segment not found")

    # Build updated file content
    file_content = {
        "consultation_id": str(consultation_id),
        "segment_type": segment_type,
        "storage_format": segment_record.data[0]["storage_format"],
        "segment_content": edited_content,  # ⭐ Updated content
        "last_edited": datetime.now().isoformat(),
        "version": "edited",
        "metadata": {
            "expert_id": str(expert_id),
            "edited_at": datetime.now().isoformat()
        }
    }

    # Create file in OpenAI
    file_json = json.dumps(file_content, indent=2)
    file_bytes = BytesIO(file_json.encode('utf-8'))
    file_tuple = (f"{file_name}_v2.json", file_bytes)

    new_file = client.files.create(
        file=file_tuple,
        purpose="assistants"
    )

    new_file_id = new_file.id

    # 4. Update vector store
    if old_file_id:
        # Remove old file from vector store
        try:
            client.vector_stores.files.delete(
                vector_store_id=vector_store_id,
                file_id=old_file_id
            )
            print(f"Removed old file {old_file_id} from vector store")
        except Exception as e:
            print(f"Warning: Could not remove old file: {e}")

    # Add new file to vector store
    client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=new_file_id
    )

    # 5. Update database record
    if file_query.data:
        await supabase.table("documents").update({
            "openai_file_id": new_file_id,
            "updated_at": datetime.now()
        }).eq("id", file_query.data[0]["id"]).execute()
    else:
        await supabase.table("documents").insert({
            "name": file_name,
            "document_link": f"internal://segment/{consultation_id}/{segment_type}",
            "owner_id": str(expert_id),
            "openai_file_id": new_file_id,
            "doc_type": "segment"
        }).execute()

    # 6. Clean up old file from OpenAI (optional, saves storage)
    if old_file_id:
        try:
            client.files.delete(old_file_id)
            print(f"Deleted old OpenAI file {old_file_id}")
        except Exception as e:
            print(f"Warning: Could not delete old file (may be in use): {e}")

    return {
        "status": "success",
        "old_file_id": old_file_id,
        "new_file_id": new_file_id,
        "vector_store_id": vector_store_id
    }

# File size limit validation
MAX_FILE_SIZE_MB = 500  # OpenAI limit is 512 MB, use 500 for safety

async def validate_segment_size(content: str, segment_type: str) -> bool:
    """Validate segment doesn't exceed OpenAI file size limits"""
    size_bytes = len(content.encode('utf-8'))
    size_mb = size_bytes / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"Segment {segment_type} size ({size_mb:.2f} MB) exceeds {MAX_FILE_SIZE_MB} MB limit. "
                   f"Please summarize or split the content."
        )

    return True
```

---

## Field Extraction Error Handling ⭐ NEW (v2.2)

**Problem:** Extraction from 26 segments may fail for some segments.
**Solution:** Partial success handling with fallbacks and LLM-based extraction.

```python
async def extract_all_fields(segments: list) -> dict:
    """
    Extract structured fields from segments with robust error handling

    Features:
    - Partial success (continue even if some extractions fail)
    - Fallback to LLM extraction for complex fields
    - Error logging for monitoring
    - Default values for required fields
    """
    # Initialize with safe defaults
    extracted = {
        "patient_name": None,
        "patient_age": None,
        "patient_dob": None,
        "patient_gender": None,
        "patient_height": None,
        "patient_weight": None,
        "consultation_date": None,
        "chief_complaint": None,
        "diagnosis": None,
        "anxiety_level_before": None,
        "anxiety_level_after": None,
        "financial_considerations": None,
        "compliance_likelihood": None,
        # ... all other fields with None defaults
    }

    extraction_errors = []
    extraction_successes = []

    for segment in segments:
        try:
            segment_type = segment["type"]
            content = segment["content"]
            storage_format = segment["format"]

            # Normalize segment type
            normalized_type = await normalize_segment_type(segment_type)

            # Route to appropriate extractor based on segment type
            if normalized_type == "PatientDetails":
                try:
                    patient_data = extract_patient_details(content, storage_format)
                    extracted.update(patient_data)
                    extraction_successes.append(normalized_type)
                except Exception as e:
                    extraction_errors.append({
                        "segment": normalized_type,
                        "error": str(e),
                        "fallback_attempted": True
                    })
                    # Fallback: LLM extraction
                    try:
                        patient_data = await llm_extract_patient_details(content)
                        extracted.update(patient_data)
                        extraction_successes.append(f"{normalized_type}_fallback")
                    except Exception as fallback_error:
                        extraction_errors[-1]["fallback_error"] = str(fallback_error)

            elif normalized_type == "SubtextAnalysis":
                try:
                    subtext_data = extract_subtext_analysis(content, storage_format)
                    extracted.update(subtext_data)
                    extraction_successes.append(normalized_type)
                except Exception as e:
                    extraction_errors.append({
                        "segment": normalized_type,
                        "error": str(e),
                        "fallback_attempted": True
                    })
                    # Fallback: LLM extraction
                    try:
                        subtext_data = await llm_extract_subtext(content)
                        extracted.update(subtext_data)
                        extraction_successes.append(f"{normalized_type}_fallback")
                    except Exception as fallback_error:
                        extraction_errors[-1]["fallback_error"] = str(fallback_error)

            elif normalized_type == "ChiefComplaint":
                try:
                    extracted["chief_complaint"] = content.strip()
                    extraction_successes.append(normalized_type)
                except Exception as e:
                    extraction_errors.append({"segment": normalized_type, "error": str(e)})

            elif normalized_type == "Diagnosis":
                try:
                    extracted["diagnosis"] = content.strip()
                    # Try to extract ICD-10 code if present
                    icd_match = re.search(r'\b([A-Z][0-9]{2}(?:\.[0-9]{1,4})?)\b', content)
                    if icd_match:
                        extracted["icd_10_code"] = icd_match.group(1)
                    extraction_successes.append(normalized_type)
                except Exception as e:
                    extraction_errors.append({"segment": normalized_type, "error": str(e)})

            elif normalized_type == "PrescriptionData":
                try:
                    # JSON format - parse directly
                    if storage_format == "JSON":
                        extracted["medications"] = json.loads(content)
                    else:
                        # Fallback: LLM extraction
                        extracted["medications"] = await llm_extract_medications(content)
                    extraction_successes.append(normalized_type)
                except Exception as e:
                    extraction_errors.append({
                        "segment": normalized_type,
                        "error": str(e),
                        "content_preview": content[:100]
                    })

            # ... handle other segment types similarly

        except Exception as e:
            # Catastrophic error for this segment - log and continue
            extraction_errors.append({
                "segment": segment.get("type", "unknown"),
                "error": f"Catastrophic error: {str(e)}",
                "content_preview": str(segment.get("content", ""))[:100]
            })
            continue  # PARTIAL SUCCESS - continue with other segments

    # Log extraction results for monitoring
    if extraction_errors:
        await supabase.table("extraction_errors").insert({
            "consultation_id": segments[0].get("consultation_id") if segments else None,
            "timestamp": datetime.now(),
            "errors": extraction_errors,
            "successes": extraction_successes,
            "success_rate": len(extraction_successes) / (len(extraction_successes) + len(extraction_errors))
        }).execute()

    # Validate critical fields
    if not extracted.get("patient_name"):
        print("Warning: Patient name not extracted")

    if not extracted.get("consultation_date"):
        # Fallback to current timestamp
        extracted["consultation_date"] = datetime.now()

    return extracted

# LLM-based fallback extractors
async def llm_extract_patient_details(content: str) -> dict:
    """Use GPT-4o to extract patient details when structured parsing fails"""
    prompt = f"""Extract patient demographics from the following text.
Return JSON with keys: patient_name, patient_age, patient_dob, patient_gender, patient_height, patient_weight.
Use null for missing fields.

Text:
{content}

JSON:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Cheaper for extraction
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    return json.loads(response.choices[0].message.content)

async def llm_extract_subtext(content: str) -> dict:
    """Extract psychosocial factors using LLM"""
    prompt = f"""Extract psychosocial factors from the following clinical text.
Return JSON with keys: anxiety_level_before (High/Moderate/Low), anxiety_level_after,
financial_considerations, compliance_likelihood (High/Moderate/Low).
Use null for missing fields.

Text:
{content}

JSON:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )

    return json.loads(response.choices[0].message.content)
```

---

## Background Job Architecture ⭐ NEW (v2.2)

**Problem:** Creating 26 vector files per consultation synchronously blocks webhook response.
**Solution:** Async processing with FastAPI BackgroundTasks.

```python
from fastapi import BackgroundTasks

@router.post("/webhooks/pradhi")
async def handle_pradhi_webhook(
    webhook_data: dict,
    background_tasks: BackgroundTasks
):
    """
    Webhook handler with async processing

    Timeline:
    - Sync phase (< 500ms): Store segments in database
    - Async phase (< 30s): Create vector files, extract fields
    - Background phase (< 5min): Pattern analysis
    """
    try:
        # PHASE 1: Quick validation and DB insert (< 500ms)
        consultation_id = webhook_data["consultation_id"]
        segments = webhook_data["segments"]
        expert_id = webhook_data["expert_id"]

        # Store pristine segments immediately
        consultation_uuid = await store_segments_sync(
            consultation_id=consultation_id,
            segments=segments,
            expert_id=expert_id,
            org_id=webhook_data["org_id"],
            org_client_id=webhook_data["org_client_id"]
        )

        # PHASE 2: Schedule heavy lifting in background
        background_tasks.add_task(
            process_consultation_async,
            consultation_uuid=consultation_uuid,
            segments=segments,
            expert_id=expert_id,
            consultation_date=webhook_data.get("consultation_date", datetime.now())
        )

        # PHASE 3: Return immediately to Pradhi (< 500ms total)
        return {
            "status": "accepted",
            "consultation_id": consultation_id,
            "consultation_uuid": str(consultation_uuid),
            "message": "Consultation received. Processing in background."
        }

    except Exception as e:
        print(f"ERROR in webhook handler: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def store_segments_sync(
    consultation_id: str,
    segments: list,
    expert_id: UUID,
    org_id: UUID,
    org_client_id: int
) -> UUID:
    """Synchronous phase: Store segments in database only"""
    consultation_uuid = uuid.uuid4()

    # Batch insert all 26 segments
    segment_records = []
    for segment in segments:
        normalized_type = await normalize_segment_type(segment["type"])
        segment_records.append({
            "consultation_id": consultation_uuid,
            "segment_type": normalized_type,
            "storage_format": segment["format"],
            "original_content": segment["content"],
            "edited_content": None,
            "edited_by": None
        })

    # Single batch insert (faster than 26 individual inserts)
    await supabase.table("record_segments").insert(segment_records).execute()

    # Create minimal consultation record
    await supabase.table("consultations").insert({
        "id": consultation_uuid,
        "consultation_id": consultation_id,
        "expert_id": expert_id,
        "org_id": org_id,
        "org_client_id": org_client_id,
        "created_time": datetime.now(),
        "consultation_date": datetime.now()  # Will be updated in async phase
    }).execute()

    return consultation_uuid

async def process_consultation_async(
    consultation_uuid: UUID,
    segments: list,
    expert_id: UUID,
    consultation_date: datetime
):
    """
    Background task for heavy processing

    Steps:
    1. Extract structured fields (LLM calls if needed)
    2. Update consultation record
    3. Create 26 vector files in parallel
    4. Generate suggested edits (pattern application)
    """
    try:
        # Step 1: Extract fields (may use LLM, can be slow)
        extracted_fields = await extract_all_fields(segments)

        # Step 2: Update consultation with extracted data
        await supabase.table("consultations").update({
            **extracted_fields,
            "consultation_date": consultation_date,
            "full_segments_data": {seg["type"]: seg["content"] for seg in segments}
        }).eq("id", consultation_uuid).execute()

        # Step 3: Create vector files IN PARALLEL (fastest approach)
        vector_store_id = await get_expert_vector_store_id(expert_id, consultation_date)

        # Parallel file creation using asyncio.gather
        file_creation_tasks = [
            create_single_vector_file(
                consultation_id=consultation_uuid,
                segment=segment,
                vector_store_id=vector_store_id,
                expert_id=expert_id,
                extracted_fields=extracted_fields
            )
            for segment in segments
        ]

        file_ids = await asyncio.gather(*file_creation_tasks)
        print(f"Created {len(file_ids)} vector files for consultation {consultation_uuid}")

        # Step 4: Generate suggested edits (pattern application)
        # This is optional and doesn't block consultation completion
        try:
            suggested_segments = await generate_suggested_edits(
                segments=segments,
                expert_id=expert_id
            )
            # Store suggestions for UI retrieval
            await supabase.table("consultation_suggestions").insert({
                "consultation_id": consultation_uuid,
                "suggestions": suggested_segments,
                "generated_at": datetime.now()
            }).execute()
        except Exception as e:
            print(f"Warning: Could not generate suggestions: {e}")

    except Exception as e:
        # Log error but don't crash
        print(f"ERROR in background processing for {consultation_uuid}: {e}")
        await supabase.table("processing_errors").insert({
            "consultation_id": consultation_uuid,
            "error": str(e),
            "timestamp": datetime.now()
        }).execute()

async def create_single_vector_file(
    consultation_id: UUID,
    segment: dict,
    vector_store_id: str,
    expert_id: UUID,
    extracted_fields: dict
) -> str:
    """Create a single vector file for a segment"""
    normalized_type = await normalize_segment_type(segment["type"])

    file_content = {
        "consultation_id": str(consultation_id),
        "segment_type": normalized_type,
        "storage_format": segment["format"],
        "segment_content": segment["content"],
        "patient_context": {
            "org_client_id": extracted_fields.get("org_client_id"),
            "name": extracted_fields.get("patient_name"),
            "age": extracted_fields.get("patient_age"),
            "gender": extracted_fields.get("patient_gender")
        },
        "metadata": {
            "consultation_date": str(extracted_fields.get("consultation_date")),
            "expert_id": str(expert_id)
        }
    }

    # Create file
    file_json = json.dumps(file_content, indent=2)
    file_bytes = BytesIO(file_json.encode('utf-8'))
    file_name = f"consultation_{consultation_id}_segment_{normalized_type}.json"
    file_tuple = (file_name, file_bytes)

    # Upload to OpenAI
    openai_file = client.files.create(
        file=file_tuple,
        purpose="assistants"
    )

    # Add to vector store
    client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=openai_file.id
    )

    # Save to database
    await supabase.table("documents").insert({
        "name": file_name,
        "document_link": f"internal://segment/{consultation_id}/{normalized_type}",
        "owner_id": str(expert_id),
        "openai_file_id": openai_file.id,
        "doc_type": "segment"
    }).execute()

    return openai_file.id

# Performance expectations
"""
Webhook response time: < 500ms (just DB insert)
Vector file creation: ~30 seconds (26 files in parallel × ~1-2s each = ~2s total with parallelization)
Total background processing: < 60 seconds for full consultation
"""
```

---

## Privacy & Expert Isolation Guarantees

### Database-Level Isolation

**Row-Level Security Policies:**

```sql
-- Experts can only see their own edit patterns
ALTER TABLE edit_patterns ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Experts view own patterns only"
ON edit_patterns
FOR SELECT
USING (expert_id = auth.uid()::uuid);

CREATE POLICY "Experts modify own patterns only"
ON edit_patterns
FOR ALL
USING (expert_id = auth.uid()::uuid);

-- Experts can only see their own edits
ALTER TABLE consultation_edits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Experts view own edits only"
ON consultation_edits
FOR SELECT
USING (edited_by = auth.uid()::uuid);
```

### Application-Level Guarantees

**All pattern queries MUST include expert_id filter:**

```python
# ✅ CORRECT: Expert-scoped query
patterns = await supabase.table("edit_patterns").select("*").eq(
    "expert_id", expert_id  # Always filter by expert
).eq("segment_type", segment_type).execute()

# ❌ WRONG: Never query patterns without expert filter
patterns = await supabase.table("edit_patterns").select("*").eq(
    "segment_type", segment_type  # Missing expert_id filter!
).execute()
```

**Code review checklist:**
- [ ] All `edit_patterns` queries filter by `expert_id`
- [ ] All `consultation_edits` analysis filters by `edited_by`
- [ ] Pattern application only uses current expert's patterns
- [ ] No aggregation across experts
- [ ] No domain-level or org-level pattern sharing

### Isolation Verification Tests

```python
async def test_expert_isolation():
    """
    Unit test to verify expert pattern isolation
    """
    expert_1 = "uuid-expert-1"
    expert_2 = "uuid-expert-2"

    # Expert 1 makes edits
    await track_edit(
        consultation_id="CONS001",
        segment_type="Diagnosis",
        original_content="diabetis",
        edited_content="diabetes",
        edited_by=expert_1
    )

    # Expert 2 makes different edits
    await track_edit(
        consultation_id="CONS002",
        segment_type="Diagnosis",
        original_content="diabetis",
        edited_content="diabetes mellitus",  # Different preference
        edited_by=expert_2
    )

    # Wait for pattern analysis
    await analyze_expert_edit_pattern_async(expert_1, "Diagnosis")
    await analyze_expert_edit_pattern_async(expert_2, "Diagnosis")

    # Get Expert 1's patterns
    patterns_1 = await supabase.table("edit_patterns").select("*").eq(
        "expert_id", expert_1
    ).eq("segment_type", "Diagnosis").execute()

    # Get Expert 2's patterns
    patterns_2 = await supabase.table("edit_patterns").select("*").eq(
        "expert_id", expert_2
    ).eq("segment_type", "Diagnosis").execute()

    # Verify isolation: patterns are different
    assert patterns_1.data[0]["patterns"]["common_corrections"]["diabetis"] == "diabetes"
    assert patterns_2.data[0]["patterns"]["common_corrections"]["diabetis"] == "diabetes mellitus"

    # Verify no cross-contamination
    assert expert_1 not in str(patterns_2.data)
    assert expert_2 not in str(patterns_1.data)

    print("✅ Expert isolation verified")
```

---

## Expert Isolation Architecture Summary

| Aspect | Implementation | Isolation Level |
|--------|----------------|-----------------|
| **Edit Storage** | `consultation_edits.edited_by` | ✅ Per expert |
| **Pattern Analysis** | Filter by `expert_id` in all queries | ✅ Per expert |
| **Pattern Storage** | `edit_patterns.expert_id` (unique constraint) | ✅ Per expert |
| **Pattern Application** | Only apply patterns from same expert | ✅ Per expert |
| **Learning Dashboard** | Isolated stats per expert | ✅ Per expert |
| **Database Security** | Row-level security policies | ✅ Per expert |
| **Vector Files** | Separate per expert (Tier 2, 3) | ✅ Per expert |
| **Future Fine-Tuning** | One model per expert (optional) | ✅ Per expert |

---

## Caching Strategy ⭐ NEW (v2.2)

**Problem:** Pattern queries can be slow, especially with high edit volumes.
**Solution:** Redis caching for frequently accessed patterns + rate limiting.

```python
import redis
from functools import lru_cache
import hashlib

# Redis client setup
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

PATTERN_CACHE_TTL = 3600  # 1 hour

async def get_expert_patterns_cached(expert_id: UUID, segment_type: str) -> dict:
    """
    Get expert patterns with Redis caching

    Cache key format: patterns:{expert_id}:{segment_type}
    TTL: 1 hour (patterns don't change frequently)
    """
    cache_key = f"patterns:{expert_id}:{segment_type}"

    # Try cache first
    cached = redis_client.get(cache_key)
    if cached:
        print(f"Cache HIT for {cache_key}")
        return json.loads(cached)

    print(f"Cache MISS for {cache_key}")

    # Cache miss - fetch from database
    patterns = await supabase.table("edit_patterns").select("*").eq(
        "expert_id", expert_id
    ).eq("segment_type", segment_type).execute()

    if patterns.data and len(patterns.data) > 0:
        pattern_data = patterns.data[0]

        # Cache for 1 hour
        redis_client.setex(
            cache_key,
            PATTERN_CACHE_TTL,
            json.dumps(pattern_data)
        )

        return pattern_data

    return None

async def invalidate_pattern_cache(expert_id: UUID, segment_type: str):
    """Invalidate cache when patterns are updated"""
    cache_key = f"patterns:{expert_id}:{segment_type}"
    redis_client.delete(cache_key)
    print(f"Cache INVALIDATED for {cache_key}")

# Update pattern analysis to invalidate cache
async def update_expert_patterns(
    expert_id: UUID,
    segment_type: str,
    patterns: dict,
    sample_count: int,
    confidence_score: float
):
    """Update patterns and invalidate cache"""
    await supabase.table("edit_patterns").upsert({
        "expert_id": expert_id,
        "segment_type": segment_type,
        "patterns": patterns,
        "sample_count": sample_count,
        "confidence_score": confidence_score,
        "last_updated": datetime.now()
    }).execute()

    # Invalidate cache so next request gets fresh data
    await invalidate_pattern_cache(expert_id, segment_type)

# Rate limiting for pattern analysis
PATTERN_ANALYSIS_MIN_EDITS = 10  # Batch analyze every 10 edits

async def should_analyze_patterns(expert_id: UUID, segment_type: str) -> bool:
    """Check if we have enough unanalyzed edits to trigger analysis"""
    unanalyzed_count = await supabase.table("consultation_edits").select(
        "id", count="exact"
    ).eq("edited_by", expert_id).eq(
        "segment_type", segment_type
    ).eq("pattern_analyzed", False).execute()

    count = unanalyzed_count.count or 0

    return count >= PATTERN_ANALYSIS_MIN_EDITS

# Updated track_edit with rate limiting
async def track_edit_with_caching(
    consultation_id: UUID,
    segment_type: str,
    original_content: str,
    edited_content: str,
    edited_by: UUID,
    edit_reason: str = None
):
    """Track edit with intelligent pattern analysis triggering"""
    # ... existing track_edit logic ...

    # Only trigger pattern analysis if we have enough edits
    if await should_analyze_patterns(edited_by, segment_type):
        asyncio.create_task(
            analyze_expert_edit_pattern_async(
                expert_id=edited_by,
                segment_type=segment_type
            )
        )
    else:
        print(f"Waiting for more edits before analyzing ({await get_unanalyzed_count(edited_by, segment_type)}/{PATTERN_ANALYSIS_MIN_EDITS})")

# Cache statistics (for monitoring)
async def get_cache_stats() -> dict:
    """Get Redis cache hit/miss statistics"""
    info = redis_client.info('stats')

    return {
        "keyspace_hits": info.get('keyspace_hits', 0),
        "keyspace_misses": info.get('keyspace_misses', 0),
        "hit_rate": round(
            info.get('keyspace_hits', 0) /
            (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1)) * 100,
            2
        ),
        "total_keys": redis_client.dbsize(),
        "memory_used": info.get('used_memory_human')
    }
```

**Cache Invalidation Strategy:**
- **Invalidate on update:** When patterns are updated, delete cache immediately
- **TTL-based expiration:** 1 hour TTL ensures stale data doesn't persist
- **Selective caching:** Only cache `edit_patterns` (stable data), not `consultation_edits` (constantly changing)

**Performance Impact:**
- Cache hit: < 5ms (vs ~50-100ms database query)
- 90%+ cache hit rate expected (patterns don't change frequently)
- 10-20x speedup for pattern application

---

## Analytics Performance Optimization ⭐ NEW (v2.2)

**Problem:** Analytics queries with ILIKE are slow.
**Solution:** Full-text search indexes + materialized views.

### Full-Text Search Indexes

```sql
-- Add GIN indexes for full-text search (MUCH faster than ILIKE)
CREATE INDEX idx_consultations_diagnosis_fts
    ON consultations USING GIN (to_tsvector('english', diagnosis));

CREATE INDEX idx_consultations_chief_complaint_fts
    ON consultations USING GIN (to_tsvector('english', chief_complaint));

-- Composite index for common date + expert queries
CREATE INDEX idx_consultations_expert_date_range
    ON consultations (expert_id, consultation_date DESC)
    INCLUDE (anxiety_level_before, anxiety_level_after, compliance_likelihood);

-- Index for psychosocial analytics
CREATE INDEX idx_consultations_psychosocial
    ON consultations (anxiety_level_before, anxiety_level_after, compliance_likelihood)
    WHERE anxiety_level_before IS NOT NULL;
```

### Materialized Views for Common Analytics

```sql
-- Materialized view for anxiety improvement tracking
CREATE MATERIALIZED VIEW mv_anxiety_improvements AS
SELECT
    expert_id,
    DATE_TRUNC('month', consultation_date) as month,
    COUNT(*) as total_consultations,
    COUNT(*) FILTER (
        WHERE anxiety_level_before = 'High'
        AND anxiety_level_after IN ('Moderate', 'Low')
    ) as high_to_lower,
    COUNT(*) FILTER (
        WHERE anxiety_level_before = 'Moderate'
        AND anxiety_level_after = 'Low'
    ) as moderate_to_low,
    ROUND(
        COUNT(*) FILTER (
            WHERE anxiety_level_before > anxiety_level_after
        )::numeric / NULLIF(COUNT(*), 0)::numeric * 100,
        2
    ) as improvement_rate
FROM consultations
WHERE anxiety_level_before IS NOT NULL
  AND anxiety_level_after IS NOT NULL
GROUP BY expert_id, DATE_TRUNC('month', consultation_date);

-- Unique index for fast refresh
CREATE UNIQUE INDEX ON mv_anxiety_improvements (expert_id, month);

-- Materialized view for diagnosis trends
CREATE MATERIALIZED VIEW mv_diagnosis_trends AS
SELECT
    expert_id,
    org_id,
    DATE_TRUNC('month', consultation_date) as month,
    diagnosis,
    COUNT(*) as diagnosis_count,
    AVG(patient_age) as avg_patient_age,
    COUNT(DISTINCT org_client_id) as unique_patients
FROM consultations
WHERE diagnosis IS NOT NULL
GROUP BY expert_id, org_id, DATE_TRUNC('month', consultation_date), diagnosis
HAVING COUNT(*) > 1;  -- Filter out one-off diagnoses

CREATE UNIQUE INDEX ON mv_diagnosis_trends (expert_id, org_id, month, diagnosis);

-- Auto-refresh function
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_anxiety_improvements;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_diagnosis_trends;
END;
$$ LANGUAGE plpgsql;

-- Schedule refresh (using pg_cron or external scheduler)
-- SELECT cron.schedule('refresh-analytics', '0 * * * *', 'SELECT refresh_analytics_views()');
```

### Optimized Analytics Queries

```python
# BEFORE (slow): Using ILIKE
async def analytics_premature_births_slow(months: int = 6):
    query = """
    SELECT COUNT(DISTINCT consultation_id)
    FROM consultations
    WHERE consultation_date > NOW() - INTERVAL '{months} months'
      AND (
        diagnosis ILIKE '%premature%'
        OR diagnosis ILIKE '%preterm%'
      )
    """
    # Execution time: ~2-5 seconds with 100K rows

# AFTER (fast): Using full-text search
async def analytics_premature_births_optimized(months: int = 6, expert_id: UUID = None):
    """
    Optimized with full-text search index

    10-100x faster than ILIKE!
    """
    query = """
    SELECT
        COUNT(DISTINCT consultation_id) as premature_count,
        AVG(patient_age) as avg_mother_age,
        ARRAY_AGG(DISTINCT icd_10_code) FILTER (WHERE icd_10_code IS NOT NULL) as icd_codes
    FROM consultations
    WHERE consultation_date > NOW() - INTERVAL '{months} months'
      {expert_filter}
      AND to_tsvector('english', diagnosis) @@ to_tsquery('english', 'premature | preterm | preemie')
    """

    expert_filter = f"AND expert_id = '{expert_id}'" if expert_id else ""

    result = await supabase.rpc("execute_query", {
        "query": query.format(months=months, expert_filter=expert_filter)
    }).execute()

    # Execution time: ~50-200ms with 100K rows (10-100x faster!)

    return result.data

# Using materialized views for anxiety analytics
async def analytics_anxiety_improvement_optimized(expert_id: UUID = None, months: int = 3):
    """
    Query pre-aggregated materialized view

    100-1000x faster than scanning raw consultations!
    """
    query = """
    SELECT
        month,
        SUM(total_consultations) as total,
        SUM(high_to_lower) as high_improved,
        SUM(moderate_to_low) as moderate_improved,
        ROUND(AVG(improvement_rate), 2) as avg_improvement_rate
    FROM mv_anxiety_improvements
    WHERE month >= DATE_TRUNC('month', NOW() - INTERVAL '{months} months')
      {expert_filter}
    GROUP BY month
    ORDER BY month DESC
    """

    expert_filter = f"AND expert_id = '{expert_id}'" if expert_id else ""

    result = await supabase.rpc("execute_query", {
        "query": query.format(months=months, expert_filter=expert_filter)
    }).execute()

    # Execution time: < 10ms (queries pre-aggregated data!)

    return result.data
```

### Performance Comparison

| Query Type | Before (ILIKE) | After (FTS + Materialized Views) | Speedup |
|------------|----------------|----------------------------------|---------|
| Diagnosis search | 2-5 seconds | 50-200 ms | **10-100x** |
| Anxiety analytics | 1-3 seconds | < 10 ms | **100-300x** |
| Trend analysis | 5-10 seconds | < 50 ms | **100-200x** |

### Monitoring Query Performance

```python
async def explain_query(query: str) -> dict:
    """Run EXPLAIN ANALYZE on a query to check performance"""
    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"

    result = await supabase.rpc("execute_query", {
        "query": explain_query
    }).execute()

    plan = result.data[0]['QUERY PLAN'][0]

    return {
        "execution_time_ms": plan['Execution Time'],
        "planning_time_ms": plan['Planning Time'],
        "total_cost": plan['Plan']['Total Cost'],
        "uses_index": 'Index Scan' in str(plan),
        "rows_processed": plan['Plan'].get('Actual Rows', 0)
    }

# Example usage
query_performance = await explain_query("""
    SELECT COUNT(*) FROM consultations
    WHERE to_tsvector('english', diagnosis) @@ to_tsquery('english', 'diabetes')
""")
# Returns: {"execution_time_ms": 45, "uses_index": True, ...}
```

---

## Search Implementation

### 1. Semantic Search

```python
async def semantic_search(query: str, org_client_id: int = None, expert_id: UUID = None):
    """
    Natural language queries like:
    "What did the patient mainly complain about?"
    """
    # Generate embedding
    embedding = await get_embedding(query)

    # Analyze query to determine target segments
    segment_hints = analyze_query_intent(query)
    # "complain" → ["Chief Complaint(s)", "Associated Symptoms"]

    # Search relevant segment vector files
    filters = {"segment_type": {"$in": segment_hints}}
    if org_client_id:
        filters["patient_context.org_client_id"] = org_client_id
    if expert_id:
        filters["metadata.expert_id"] = str(expert_id)

    results = await vector_store.search(
        embedding=embedding,
        filter=filters,
        top_k=10
    )

    return results
```

### 2. Composite Filter Queries

```python
# Query: "In the last 6 months, how many babies were born pre-maturely?"
async def analytics_premature_births(months: int = 6, expert_id: UUID = None):
    query = """
    SELECT
        COUNT(DISTINCT consultation_id) as premature_count,
        AVG(patient_age) as avg_mother_age,
        array_agg(DISTINCT diagnosis) as all_diagnoses
    FROM consultations
    WHERE consultation_date > NOW() - INTERVAL '{months} months'
      {expert_filter}
      AND (
        diagnosis ILIKE '%premature%'
        OR diagnosis ILIKE '%preterm%'
        OR diagnosis ILIKE '%preemie%'
        OR full_segments_data->>'Diagnosis' ILIKE '%premature%'
      )
    """

    expert_filter = f"AND expert_id = '{expert_id}'" if expert_id else ""

    result = await supabase.rpc("execute_query", {
        "query": query.format(months=months, expert_filter=expert_filter)
    }).execute()
    return result.data

# Query: "How many consultations showed anxiety improvement?"
async def analytics_anxiety_improvement(months: int = None, expert_id: UUID = None):
    query = """
    SELECT
        COUNT(*) as total_improved,
        COUNT(*) FILTER (
            WHERE anxiety_level_before = 'High'
            AND anxiety_level_after IN ('Moderate', 'Low')
        ) as high_to_lower,
        COUNT(*) FILTER (
            WHERE anxiety_level_before = 'Moderate'
            AND anxiety_level_after = 'Low'
        ) as moderate_to_low,
        ROUND(AVG(
            CASE
                WHEN anxiety_level_before = 'High' AND anxiety_level_after = 'Moderate' THEN 1
                WHEN anxiety_level_before = 'High' AND anxiety_level_after = 'Low' THEN 2
                WHEN anxiety_level_before = 'Moderate' AND anxiety_level_after = 'Low' THEN 1
                ELSE 0
            END
        ), 2) as avg_improvement_score
    FROM consultations
    WHERE anxiety_level_before IS NOT NULL
      AND anxiety_level_after IS NOT NULL
      {date_filter}
      {expert_filter}
    """

    date_filter = f"AND consultation_date > NOW() - INTERVAL '{months} months'" if months else ""
    expert_filter = f"AND expert_id = '{expert_id}'" if expert_id else ""

    result = await supabase.rpc("execute_query", {
        "query": query.format(date_filter=date_filter, expert_filter=expert_filter)
    }).execute()
    return result.data
```

---

## Migration Strategy

### Phase 1: Schema Creation

```sql
-- 1. Create new tables (in order due to foreign keys)
CREATE TABLE IF NOT EXISTS record_segments (...);
CREATE TABLE IF NOT EXISTS consultations (...);
CREATE TABLE IF NOT EXISTS consultation_edits (...);
CREATE TABLE IF NOT EXISTS edit_patterns (...);  -- ⭐ NEW
CREATE TABLE IF NOT EXISTS ehr_export_configs (...);
CREATE TABLE IF NOT EXISTS record_merge_configs (...);
CREATE TABLE IF NOT EXISTS merged_records (...);

-- 2. Add new columns to existing clients table (backward compatible)
ALTER TABLE clients ADD COLUMN IF NOT EXISTS demographics JSONB;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS current_diagnosis TEXT;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_consultation_id UUID;

-- 3. Create row-level security policies
-- (See Privacy & Expert Isolation section)
```

### Phase 2: Data Migration

**Keep `client_data_jsonb` for backward compatibility**

```python
async def migrate_existing_data():
    """
    Migrate existing client_data_jsonb to new schema
    Preserves backward compatibility
    """
    clients = await supabase.table("clients").select("*").execute()

    for client in clients.data:
        if not client.get("client_data_jsonb"):
            continue

        # Process and create consultation records
        # (See original plan for full migration code)

        # Important: Keep client_data_jsonb intact
        # Only update new fields
        await supabase.table("clients").update({
            "demographics": extract_demographics(client["client_data_jsonb"])
        }).eq("id", client["id"]).execute()
```

---

## Implementation Timeline ⭐ UPDATED (v2.2)

### Phase 0: Infrastructure Setup (Week 1) ⭐ NEW
- **Redis setup** for caching layer
- **Background job infrastructure** (FastAPI BackgroundTasks or Celery)
- **Monitoring tools** (query performance, cache hit rates)
- **Development environment** configuration

### Phase 1: Core Schema & Infrastructure (Week 1-2)
- Create all **8 tables** (added `segment_type_mappings`) with proper indexes
- Implement row-level security policies
- Add **CHECK constraints** and NOT NULL constraints
- Write migration scripts
- Set up webhook endpoint `/webhooks/pradhi` with background tasks
- Seed segment mapping table with all 26 segments

### Phase 2: Field Extraction & Storage (Week 2-3)
- Implement parsers for all 26 segment types
- Build extraction pipeline with **error handling and fallbacks**
- Create vector file generation with **parallel processing**
- Implement **monthly vector store rollover** logic
- Test with sample Pradhi data
- Implement **LLM-based fallback extractors**

### Phase 3: Expert-Scoped Adaptive Learning (Week 3-4)
- Implement edit tracking with **pristine original storage**
- Build pattern analysis engine (expert-scoped)
- Create pattern application logic (**display-only**, not storage)
- Implement **vector file update mechanism** (delete-and-recreate)
- Build expert learning dashboard
- Add **caching layer** for patterns (Redis)

### Phase 4: Search & Analytics (Week 4-5)
- Semantic search implementation
- Composite filter queries
- Hybrid search
- **Full-text search indexes** (GIN indexes for diagnosis, chief complaint)
- **Materialized views** for common analytics
- Analytics queries with expert filtering
- **Query performance monitoring**

### Phase 5: EHR Export & Merging (Week 5-6)
- Config management for exports
- HL7/JSON/FHIR export functions
- Merge config system
- Merge execution engine

### Phase 6: Performance Optimization (Week 6-7) ⭐ NEW
- **Cache tuning** and monitoring
- **Materialized view refresh** scheduling
- **Vector store archival** automation
- Query optimization based on EXPLAIN ANALYZE
- Load testing (100 consultations/day simulation)

### Phase 7: Testing & QA (Week 7)
- Expert isolation verification tests
- Search performance testing (verify 10-100x speedup)
- Export validation
- **Cache performance** testing
- **Background job** reliability testing
- UAT with sample experts

**Total Timeline: 7 weeks** (was 6 weeks)

---

## Open Questions

1. **Pradhi Webhook Security:**
   - How is the webhook authenticated?
   - IP whitelist? API key? Signature verification?

2. **Segment Structure Versioning:**
   - Can Pradhi change segment structure over time?
   - How do we handle schema evolution?

3. **Expert Model Training:**
   - Should we implement fine-tuned models per expert in Phase 1?
   - Or defer to future enhancement?

4. **Pattern Confidence Threshold:**
   - What's the minimum confidence to apply patterns? (Currently 0.7)
   - Should this be configurable per expert?

5. **Cross-Expert Learning (Future):**
   - Should we eventually allow opt-in expert pattern sharing?
   - E.g., "Senior doctors can share patterns with residents"

6. **Storage Limits:**
   - OpenAI vector store file limits?
   - Supabase storage quota for 26 files per consultation?

---

## Success Metrics

**RAG Performance:**
- Retrieval precision > 90% for segment-level queries
- Query response time < 2 seconds

**Adaptive Learning Effectiveness:**
- Edit frequency decreases > 20% after 30 consultations per expert
- Pattern confidence > 0.8 after 50 edits per segment type
- Expert satisfaction score > 4.5/5

**Expert Isolation:**
- Zero cross-expert pattern contamination (verified by tests)
- Each expert's learning curve independent

**Export Success:**
- HL7 export accuracy > 95%
- Configurable field mapping covers 100% of use cases

**System Performance:**
- Webhook processing < 5 seconds for 26 segments
- Pattern analysis completes < 10 seconds
- Dashboard loads < 1 second

---

**End of Enhanced Planning Document v2.1**

---

## Quick Reference

**Key Files:**
- Planning: `/src/db/planning/client-storage-redesign-ENHANCED-2025-10-18.md`
- Schema: `/src/db/schema_segments_enhanced.sql` (to be created)

**Key Tables:**
1. `record_segments` - 26 segments with edit tracking
2. `consultations` - Aggregated structured view
3. `consultation_edits` - Expert-attributed edits
4. `edit_patterns` - **Expert-scoped** learned patterns ⭐
5. `ehr_export_configs` - Export configurations
6. `record_merge_configs` - Merge strategies
7. `merged_records` - Materialized merges

**Critical Design Principles:**
✅ Expert-level isolation (no cross-contamination)
✅ Privacy-preserving (row-level security)
✅ Backward compatible (keeps `client_data_jsonb`)
✅ Ultra-granular RAG (26 files per consultation)
✅ Configurable everything (exports, merges, patterns)
