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
}
