package com.example.wooddetect.service;

import com.example.wooddetect.config.QualityScoringProperties;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class QualityScoringServiceTest {

    private final QualityScoringService service = new QualityScoringService(new QualityScoringProperties());

    @Test
    void returnsFullScoreForImageWithoutDefects() {
        QualityScoringService.Assessment result = service.assess(List.of(), 1000, 500);

        assertEquals(100.0, result.score());
        assertEquals("A", result.grade());
        assertEquals(0.0, result.defectAreaRatio());
        assertTrue(result.defectCounts().isEmpty());
        assertTrue(result.deductions().isEmpty());
    }

    @Test
    void calculatesCountsUnionAreaMaximumAreaAndDeductionReasons() {
        QualityScoringService.Assessment result = service.assess(List.of(
                new QualityScoringService.QualityBox("split", 0, 0, 50, 50),
                new QualityScoringService.QualityBox("dry_knot", 25, 0, 75, 50)
        ), 100, 100);

        assertEquals(1, result.defectCounts().get("split"));
        assertEquals(1, result.defectCounts().get("dry_knot"));
        assertEquals(0.375, result.defectAreaRatio());
        assertEquals(0.25, result.maxDefectAreaRatio());
        assertEquals(66.62, result.score());
        assertEquals("C", result.grade());
        assertEquals(4, result.deductions().size());
    }

    @Test
    void clipsBoxesToImageAndUsesConfiguredUnknownWeight() {
        QualityScoringProperties properties = new QualityScoringProperties();
        properties.setUnknownCategoryWeight(10.0);
        QualityScoringService customService = new QualityScoringService(properties);

        QualityScoringService.Assessment result = customService.assess(List.of(
                new QualityScoringService.QualityBox("new_defect", -20, -30, 20, 10)
        ), 100, 100);

        assertEquals(0.02, result.defectAreaRatio());
        assertEquals(88.8, result.score());
        assertEquals("B", result.grade());
    }

    @Test
    void assignsGradesAtConfiguredBoundaries() {
        assertEquals("A", assessWithCategoryPenalty(10).grade());
        assertEquals("B", assessWithCategoryPenalty(25).grade());
        assertEquals("C", assessWithCategoryPenalty(40).grade());
        assertEquals("D", assessWithCategoryPenalty(40.01).grade());
    }

    private QualityScoringService.Assessment assessWithCategoryPenalty(double penalty) {
        QualityScoringProperties properties = new QualityScoringProperties();
        properties.setCategoryWeights(Map.of("split", penalty));
        properties.setAreaPenaltyPerPercent(0);
        properties.setMaxAreaPenaltyPerPercent(0);
        return new QualityScoringService(properties).assess(List.of(
                new QualityScoringService.QualityBox("split", 0, 0, 1, 1)
        ), 100, 100);
    }
}
