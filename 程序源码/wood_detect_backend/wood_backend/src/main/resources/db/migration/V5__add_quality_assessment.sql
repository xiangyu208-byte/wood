ALTER TABLE detect_record
    ADD COLUMN quality_score DECIMAL(5,2) NULL AFTER image_height,
    ADD COLUMN quality_grade VARCHAR(1) NULL AFTER quality_score,
    ADD COLUMN defect_area_ratio DOUBLE NULL AFTER quality_grade,
    ADD COLUMN max_defect_area_ratio DOUBLE NULL AFTER defect_area_ratio,
    ADD COLUMN defect_counts_json VARCHAR(2000) NULL AFTER max_defect_area_ratio,
    ADD COLUMN quality_deductions_json TEXT NULL AFTER defect_counts_json,
    ADD COLUMN quality_rule_version VARCHAR(64) NULL AFTER quality_deductions_json,
    ADD COLUMN quality_disclaimer VARCHAR(500) NULL AFTER quality_rule_version,
    ADD INDEX idx_detect_record_quality_grade (quality_grade),
    ADD INDEX idx_detect_record_quality_score (quality_score);
