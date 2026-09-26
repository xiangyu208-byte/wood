package com.example.wooddetect.config;

import jakarta.annotation.PostConstruct;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.Map;

@Data
@Component
@ConfigurationProperties(prefix = "quality-scoring")
public class QualityScoringProperties {

    private double baseScore = 100.0;
    private Map<String, Double> categoryWeights = defaultWeights();
    private double unknownCategoryWeight = 3.0;
    private double areaPenaltyPerPercent = 0.35;
    private double maxAreaPenaltyPerPercent = 0.25;
    private double totalAreaPenaltyCap = 35.0;
    private double maxAreaPenaltyCap = 20.0;
    private double gradeAMin = 90.0;
    private double gradeBMin = 75.0;
    private double gradeCMin = 60.0;
    private String ruleVersion = "WOOD-QS-1.0";
    private String disclaimer = "质量分级为本项目内部评价规则，仅用于结果比较和人工复核参考，不属于行业强制标准。";

    @PostConstruct
    void validate() {
        if (baseScore <= 0 || baseScore > 100) {
            throw new IllegalStateException("quality-scoring.base-score 必须在 0 到 100 之间");
        }
        if (!(gradeAMin > gradeBMin && gradeBMin > gradeCMin && gradeCMin >= 0)) {
            throw new IllegalStateException("质量等级阈值必须满足 A > B > C >= 0");
        }
        if (areaPenaltyPerPercent < 0 || maxAreaPenaltyPerPercent < 0
                || totalAreaPenaltyCap < 0 || maxAreaPenaltyCap < 0 || unknownCategoryWeight < 0) {
            throw new IllegalStateException("质量评分权重和惩罚参数不能为负数");
        }
        categoryWeights.forEach((name, weight) -> {
            if (weight == null || weight < 0 || !Double.isFinite(weight)) {
                throw new IllegalStateException("缺陷类别权重不合法：" + name);
            }
        });
    }

    private static Map<String, Double> defaultWeights() {
        Map<String, Double> weights = new LinkedHashMap<>();
        weights.put("split", 8.0);
        weights.put("dry_knot", 6.0);
        weights.put("edge_knot", 5.0);
        weights.put("wave", 3.0);
        weights.put("sound_knot", 2.5);
        weights.put("small_knot", 2.0);
        weights.put("suspected_anomaly", 2.0);
        return weights;
    }
}
