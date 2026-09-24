ALTER TABLE detect_record
    ADD COLUMN model_mode VARCHAR(32) NOT NULL DEFAULT 'STANDARD' AFTER source_type,
    ADD COLUMN confidence_threshold DOUBLE NOT NULL DEFAULT 0.25 AFTER model_mode,
    ADD COLUMN inference_precision VARCHAR(16) NOT NULL DEFAULT 'AUTO' AFTER confidence_threshold;

ALTER TABLE detect_batch
    ADD COLUMN cancelled_count INT NOT NULL DEFAULT 0 AFTER fail_count;
