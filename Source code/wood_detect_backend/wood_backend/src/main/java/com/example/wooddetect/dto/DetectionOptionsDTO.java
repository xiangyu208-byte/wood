package com.example.wooddetect.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class DetectionOptionsDTO {
    private String modelMode;
    private Double confidenceThreshold;
    private String inferencePrecision;
    private String materialBatch;

    public DetectionOptionsDTO(String modelMode, Double confidenceThreshold, String inferencePrecision) {
        this(modelMode, confidenceThreshold, inferencePrecision, null);
    }
}
