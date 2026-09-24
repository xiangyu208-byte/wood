CREATE TABLE IF NOT EXISTS detect_record (
    id BIGINT NOT NULL AUTO_INCREMENT,
    image_name VARCHAR(255) NOT NULL,
    image_path VARCHAR(1024) NOT NULL,
    image_url VARCHAR(1024) NOT NULL,
    result_image_path VARCHAR(1024) NULL,
    result_image_url VARCHAR(1024) NULL,
    total_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    error_message VARCHAR(2000) NULL,
    batch_no VARCHAR(128) NULL,
    source_type VARCHAR(32) NULL,
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_detect_record_create_time (create_time),
    INDEX idx_detect_record_status (status),
    INDEX idx_detect_record_batch_no (batch_no),
    INDEX idx_detect_record_source_type (source_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS detect_detail (
    id BIGINT NOT NULL AUTO_INCREMENT,
    record_id BIGINT NOT NULL,
    class_name VARCHAR(128) NOT NULL,
    confidence DOUBLE NOT NULL,
    x1 INT NOT NULL,
    y1 INT NOT NULL,
    x2 INT NOT NULL,
    y2 INT NOT NULL,
    create_time DATETIME NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_detect_detail_record_id (record_id),
    INDEX idx_detect_detail_class_name (class_name),
    CONSTRAINT fk_detect_detail_record
        FOREIGN KEY (record_id) REFERENCES detect_record (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
