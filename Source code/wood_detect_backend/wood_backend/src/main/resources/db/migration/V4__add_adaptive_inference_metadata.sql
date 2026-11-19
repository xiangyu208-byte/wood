ALTER TABLE detect_record
    ADD COLUMN actual_mode VARCHAR(32) NULL AFTER model_mode,
    ADD COLUMN decision_reason VARCHAR(64) NULL AFTER actual_mode,
    ADD COLUMN inference_duration_ms BIGINT NULL AFTER inference_precision,
    ADD COLUMN tile_count INT NOT NULL DEFAULT 1 AFTER inference_duration_ms,
    ADD COLUMN image_width INT NULL AFTER tile_count,
    ADD COLUMN image_height INT NULL AFTER image_width;
