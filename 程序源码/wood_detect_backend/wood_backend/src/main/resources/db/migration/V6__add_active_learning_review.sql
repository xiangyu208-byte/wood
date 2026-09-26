ALTER TABLE detect_record
    ADD COLUMN model_version VARCHAR(128) NULL AFTER inference_precision,
    ADD COLUMN min_confidence DOUBLE NULL AFTER model_version,
    ADD COLUMN review_needed TINYINT(1) NOT NULL DEFAULT 0 AFTER min_confidence,
    ADD COLUMN review_reason VARCHAR(64) NULL AFTER review_needed,
    ADD COLUMN review_status VARCHAR(32) NOT NULL DEFAULT 'UNREVIEWED' AFTER review_reason,
    ADD COLUMN review_comment VARCHAR(1000) NULL AFTER review_status,
    ADD COLUMN reviewed_at DATETIME NULL AFTER review_comment,
    ADD INDEX idx_detect_record_model_version (model_version),
    ADD INDEX idx_detect_record_review_status (review_status),
    ADD INDEX idx_detect_record_review_queue (review_needed, review_status);

CREATE TABLE IF NOT EXISTS detect_review_annotation (
    id BIGINT NOT NULL AUTO_INCREMENT,
    record_id BIGINT NOT NULL,
    original_detail_id BIGINT NULL,
    class_name VARCHAR(128) NOT NULL,
    confidence DOUBLE NULL,
    x1 INT NOT NULL,
    y1 INT NOT NULL,
    x2 INT NOT NULL,
    y2 INT NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    create_time DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_review_annotation_record_id (record_id),
    CONSTRAINT fk_review_annotation_record
        FOREIGN KEY (record_id) REFERENCES detect_record (id) ON DELETE CASCADE,
    CONSTRAINT fk_review_annotation_original_detail
        FOREIGN KEY (original_detail_id) REFERENCES detect_detail (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
