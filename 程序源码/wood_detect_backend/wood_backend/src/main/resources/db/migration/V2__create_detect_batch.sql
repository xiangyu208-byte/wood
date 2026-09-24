CREATE TABLE IF NOT EXISTS detect_batch (
    id BIGINT NOT NULL AUTO_INCREMENT,
    batch_no VARCHAR(128) NOT NULL,
    total_count INT NOT NULL DEFAULT 0,
    processed_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    fail_count INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    create_time DATETIME NOT NULL,
    update_time DATETIME NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_detect_batch_batch_no (batch_no),
    INDEX idx_detect_batch_create_time (create_time),
    INDEX idx_detect_batch_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
