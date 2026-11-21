CREATE TABLE material_batch (
    code VARCHAR(64) PRIMARY KEY,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE detect_record
    ADD COLUMN material_batch VARCHAR(64) NULL,
    ADD CONSTRAINT fk_detect_material_batch FOREIGN KEY (material_batch) REFERENCES material_batch(code);

CREATE TABLE inspection_analysis (
    fingerprint CHAR(64) PRIMARY KEY,
    report_text MEDIUMTEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
