package com.example.wooddetect.config;

import jakarta.annotation.PostConstruct;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Data
@Component
@ConfigurationProperties(prefix = "active-learning")
public class ActiveLearningProperties {
    private double lowConfidenceThreshold = 0.45;

    @PostConstruct
    void validate() {
        if (!Double.isFinite(lowConfidenceThreshold)
                || lowConfidenceThreshold < 0.05 || lowConfidenceThreshold > 0.95) {
            throw new IllegalStateException("active-learning.low-confidence-threshold 必须在 0.05 到 0.95 之间");
        }
    }
}
