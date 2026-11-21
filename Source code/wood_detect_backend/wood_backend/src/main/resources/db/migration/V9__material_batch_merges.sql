ALTER TABLE material_batch
    ADD COLUMN merged_into VARCHAR(64) NULL,
    ADD CONSTRAINT fk_material_batch_destination
        FOREIGN KEY (merged_into) REFERENCES material_batch(code);
