-- ============================================================================
-- Client/Patient Data Storage Redesign - Enhanced Schema v2.2
-- ============================================================================
-- Date: October 19, 2025
-- Purpose: Segment-based RAG with expert-scoped adaptive learning
-- Changes from v2.1:
--   - Added segment_type_mappings table
--   - Added CHECK constraints for data validation
--   - Added full-text search indexes
--   - Added materialized views for analytics
--   - Added caching and performance optimizations
-- ============================================================================

-- ============================================================================
-- TABLE 1: record_segments
-- Purpose: Store all 26 segments from Pradhi with edit tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS record_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL,
    segment_type VARCHAR(100) NOT NULL,
    storage_format VARCHAR(20) NOT NULL,  -- 'TEXT', 'FORMATTED', 'JSON'

    original_content TEXT NOT NULL,  -- Pristine content from Pradhi
    edited_content TEXT,             -- Expert's edited version

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    edited_at TIMESTAMP WITH TIME ZONE,
    edited_by UUID,  -- FK to experts (for isolation)

    CONSTRAINT fk_consultation FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE,
    CONSTRAINT fk_edited_by FOREIGN KEY (edited_by)
        REFERENCES experts (id),
    CONSTRAINT check_storage_format CHECK (storage_format IN ('TEXT', 'FORMATTED', 'JSON'))
);

CREATE INDEX idx_segments_consultation ON record_segments (consultation_id);
CREATE INDEX idx_segments_type ON record_segments (segment_type);
CREATE INDEX idx_segments_edited ON record_segments (edited_at) WHERE edited_content IS NOT NULL;
CREATE INDEX idx_segments_expert ON record_segments (edited_by);

-- ============================================================================
-- TABLE 2: consultations (ENHANCED)
-- Purpose: Aggregated structured view with rich extracted fields
-- ============================================================================

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
    consultation_date TIMESTAMP WITH TIME ZONE NOT NULL,  -- v2.2: Added NOT NULL
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

    -- PSYCHOSOCIAL
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
    CONSTRAINT fk_org FOREIGN KEY (org_id) REFERENCES organizations (id),

    -- v2.2: Data validation constraints
    CONSTRAINT check_anxiety_level_before
        CHECK (anxiety_level_before IN ('High', 'Moderate', 'Low') OR anxiety_level_before IS NULL),
    CONSTRAINT check_anxiety_level_after
        CHECK (anxiety_level_after IN ('High', 'Moderate', 'Low') OR anxiety_level_after IS NULL),
    CONSTRAINT check_patient_gender
        CHECK (patient_gender IN ('Male', 'Female', 'Other', 'Prefer not to say') OR patient_gender IS NULL),
    CONSTRAINT check_compliance_likelihood
        CHECK (compliance_likelihood IN ('High', 'Moderate', 'Low') OR compliance_likelihood IS NULL),
    -- ICD-10 code format validation (optional - can be disabled for performance)
    CONSTRAINT check_icd_10_format
        CHECK (icd_10_code IS NULL OR icd_10_code ~ '^[A-Z][0-9]{2}(\.[0-9]{1,4})?$')
);

-- Composite query indexes
CREATE INDEX idx_consultations_client_date ON consultations (client_id, consultation_date DESC);
CREATE INDEX idx_consultations_org_client ON consultations (org_client_id, org_id);
CREATE INDEX idx_consultations_expert_date ON consultations (expert_id, consultation_date DESC);
CREATE INDEX idx_consultations_date_range ON consultations (consultation_date);

-- v2.2: Full-text search indexes (GIN indexes)
CREATE INDEX idx_consultations_diagnosis_fts
    ON consultations USING GIN (to_tsvector('english', diagnosis));
CREATE INDEX idx_consultations_chief_complaint_fts
    ON consultations USING GIN (to_tsvector('english', chief_complaint));

-- Analytics indexes
CREATE INDEX idx_consultations_anxiety ON consultations (anxiety_level_before, anxiety_level_after)
    WHERE anxiety_level_before IS NOT NULL;
CREATE INDEX idx_consultations_compliance ON consultations (compliance_likelihood);

-- v2.2: Composite index for date + expert queries with INCLUDE
CREATE INDEX idx_consultations_expert_date_range
    ON consultations (expert_id, consultation_date DESC)
    INCLUDE (anxiety_level_before, anxiety_level_after, compliance_likelihood);

-- v2.2: Psychosocial analytics index
CREATE INDEX idx_consultations_psychosocial
    ON consultations (anxiety_level_before, anxiety_level_after, compliance_likelihood)
    WHERE anxiety_level_before IS NOT NULL;

-- ============================================================================
-- TABLE 3: consultation_edits (Expert-Scoped)
-- Purpose: Track edits for expert-specific adaptive learning
-- ============================================================================

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
    edited_by UUID NOT NULL,  -- CRITICAL: Expert who made the edit
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
CREATE INDEX idx_edits_expert ON consultation_edits (edited_by);
CREATE INDEX idx_edits_expert_segment ON consultation_edits (edited_by, segment_type);
CREATE INDEX idx_edits_analyzed ON consultation_edits (pattern_analyzed) WHERE NOT pattern_analyzed;

-- Row-level security for expert privacy
ALTER TABLE consultation_edits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Experts can only view own edits"
ON consultation_edits
FOR SELECT
USING (edited_by = auth.uid()::uuid);

-- ============================================================================
-- TABLE 4: edit_patterns (Expert-Scoped Learning)
-- Purpose: Store learned patterns per expert for adaptive learning
-- ============================================================================

CREATE TABLE IF NOT EXISTS edit_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expert_id UUID NOT NULL,  -- SCOPED PER EXPERT
    segment_type VARCHAR(100) NOT NULL,

    -- Pattern data specific to THIS EXPERT
    patterns JSONB NOT NULL,

    -- Metadata
    sample_count INT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confidence_score FLOAT,

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

CREATE POLICY "Experts modify own patterns only"
ON edit_patterns
FOR ALL
USING (expert_id = auth.uid()::uuid);

-- ============================================================================
-- TABLE 5: ehr_export_configs
-- Purpose: Configurable field mappings for EHR export
-- ============================================================================

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

-- ============================================================================
-- TABLE 6: record_merge_configs
-- Purpose: Define merging strategies
-- ============================================================================

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

-- ============================================================================
-- TABLE 7: merged_records
-- Purpose: Materialized merged views
-- ============================================================================

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

-- ============================================================================
-- TABLE 8: segment_type_mappings (v2.2 NEW)
-- Purpose: Normalize Pradhi segment names to internal names
-- ============================================================================

CREATE TABLE IF NOT EXISTS segment_type_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pradhi_name VARCHAR(100) NOT NULL UNIQUE,
    internal_name VARCHAR(100) NOT NULL UNIQUE,
    storage_format VARCHAR(20) NOT NULL,  -- 'TEXT', 'FORMATTED', 'JSON'
    description TEXT,
    extraction_priority INT DEFAULT 0,  -- Higher = more critical for extraction
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT check_storage_format_mapping CHECK (storage_format IN ('TEXT', 'FORMATTED', 'JSON'))
);

CREATE INDEX idx_segment_mappings_pradhi ON segment_type_mappings (pradhi_name);
CREATE INDEX idx_segment_mappings_internal ON segment_type_mappings (internal_name);
CREATE INDEX idx_segment_mappings_format ON segment_type_mappings (storage_format);

-- ============================================================================
-- SEED DATA: All 26 Pradhi segments
-- ============================================================================

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

-- ============================================================================
-- MATERIALIZED VIEWS FOR ANALYTICS (v2.2 NEW)
-- ============================================================================

-- Materialized view for anxiety improvement tracking
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_anxiety_improvements AS
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_anxiety_improvements_pk
    ON mv_anxiety_improvements (expert_id, month);

-- Materialized view for diagnosis trends
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_diagnosis_trends AS
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

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_diagnosis_trends_pk
    ON mv_diagnosis_trends (expert_id, org_id, month, diagnosis);

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Auto-refresh function for materialized views
CREATE OR REPLACE FUNCTION refresh_analytics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_anxiety_improvements;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_diagnosis_trends;
END;
$$ LANGUAGE plpgsql;

-- Function to get normalized segment type
CREATE OR REPLACE FUNCTION get_internal_segment_type(p_pradhi_name VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    v_internal_name VARCHAR;
BEGIN
    SELECT internal_name INTO v_internal_name
    FROM segment_type_mappings
    WHERE pradhi_name = p_pradhi_name;

    IF v_internal_name IS NULL THEN
        -- Fallback: strip special characters
        v_internal_name := REGEXP_REPLACE(p_pradhi_name, '[^a-zA-Z0-9]', '', 'g');
    END IF;

    RETURN v_internal_name;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ADDITIONAL TABLES FOR MONITORING (v2.2 NEW)
-- ============================================================================

-- Table for tracking extraction errors
CREATE TABLE IF NOT EXISTS extraction_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    errors JSONB NOT NULL,
    successes JSONB,
    success_rate FLOAT,

    CONSTRAINT fk_consultation_extraction FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE
);

CREATE INDEX idx_extraction_errors_consultation ON extraction_errors (consultation_id);
CREATE INDEX idx_extraction_errors_timestamp ON extraction_errors (timestamp DESC);

-- Table for tracking background processing errors
CREATE TABLE IF NOT EXISTS processing_errors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID,
    error TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_consultation_processing FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE
);

CREATE INDEX idx_processing_errors_timestamp ON processing_errors (timestamp DESC);

-- Table for storing consultation suggestions (pattern-based)
CREATE TABLE IF NOT EXISTS consultation_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL,
    suggestions JSONB NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT fk_consultation_suggestions FOREIGN KEY (consultation_id)
        REFERENCES consultations (id) ON DELETE CASCADE
);

CREATE INDEX idx_consultation_suggestions_id ON consultation_suggestions (consultation_id);

-- ============================================================================
-- MIGRATION NOTES
-- ============================================================================

COMMENT ON TABLE record_segments IS 'v2.2: Stores all 26 segments from Pradhi with pristine originals and tracked edits';
COMMENT ON TABLE consultations IS 'v2.2: Aggregated structured view with CHECK constraints and full-text search indexes';
COMMENT ON TABLE consultation_edits IS 'v2.2: Expert-attributed edits for adaptive learning with row-level security';
COMMENT ON TABLE edit_patterns IS 'v2.2: Expert-scoped learned patterns with caching support';
COMMENT ON TABLE segment_type_mappings IS 'v2.2: NEW - Maps Pradhi segment names to internal names';
COMMENT ON MATERIALIZED VIEW mv_anxiety_improvements IS 'v2.2: NEW - Pre-aggregated anxiety improvement analytics';
COMMENT ON MATERIALIZED VIEW mv_diagnosis_trends IS 'v2.2: NEW - Pre-aggregated diagnosis trends';

-- ============================================================================
-- END OF SCHEMA v2.2
-- ============================================================================
