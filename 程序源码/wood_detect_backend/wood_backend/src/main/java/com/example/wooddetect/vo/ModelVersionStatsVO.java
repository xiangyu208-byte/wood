package com.example.wooddetect.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ModelVersionStatsVO {
    private String modelVersion;
    private Long recordCount;
    private Long reviewedCount;
    private Long correctCount;
    private Long correctedCount;
    private Long incorrectCount;
    private Long reviewNeededCount;
    private Double averageQualityScore;
    private Double averageInferenceDurationMs;
    private LocalDateTime lastUsedAt;
    private Double confirmationRate;
    private Double correctionRate;
    private Double confirmationRateChange;
    private Double correctionRateChange;
    private Double averageQualityScoreChange;
}
