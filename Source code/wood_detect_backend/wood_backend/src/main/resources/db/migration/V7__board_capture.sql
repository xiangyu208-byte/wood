CREATE TABLE inspection_board (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(80) NOT NULL,
    face CHAR(1) NOT NULL,
    grid_rows INT NOT NULL,
    grid_cols INT NOT NULL,
    reference_image MEDIUMBLOB NULL,
    reference_type VARCHAR(32) NULL,
    UNIQUE KEY uk_board_face (code, face)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE board_capture (
    record_id BIGINT PRIMARY KEY,
    board_id BIGINT NOT NULL,
    grid_row INT NULL,
    grid_col INT NULL,
    anchor_id BIGINT NULL,
    shift_x DOUBLE NULL,
    shift_y DOUBLE NULL,
    matches_count INT NULL,
    FOREIGN KEY (board_id) REFERENCES inspection_board(id),
    FOREIGN KEY (record_id) REFERENCES detect_record(id) ON DELETE CASCADE,
    FOREIGN KEY (anchor_id) REFERENCES detect_record(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
