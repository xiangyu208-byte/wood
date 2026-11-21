package com.example.wooddetect.service;

import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.config.QualityScoringProperties;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.entity.DetectReviewAnnotation;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.example.wooddetect.mapper.DetectReviewAnnotationMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.mockito.MockMakers;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class InspectionAnalysisServiceTest {
    private final DetectRecordMapper records = mock(DetectRecordMapper.class);
    private final DetectReviewAnnotationMapper annotations = mock(DetectReviewAnnotationMapper.class);
    private final DeepSeekService model = mock(DeepSeekService.class, withSettings().mockMaker(MockMakers.SUBCLASS));
    private final MaterialBatchService batches = mock(MaterialBatchService.class, withSettings().mockMaker(MockMakers.SUBCLASS));
    private final JdbcTemplate db = mock(JdbcTemplate.class, withSettings().mockMaker(MockMakers.SUBCLASS));
    private final InspectionAnalysisService service = new InspectionAnalysisService(records, annotations,
            new QualityScoringService(new QualityScoringProperties()), batches, model, db, new ObjectMapper());

    @Test
    void correctedBoxesReplaceOriginalCountsAndFailedImagesAreExcludedFromCharts() {
        var reviewed = record(1L, "SUCCESS");
        reviewed.setReviewStatus("CORRECTED");
        reviewed.setDefectCountsJson("{\"dry_knot\":2}");
        var empty = record(2L, "SUCCESS");
        var failed = record(3L, "FAIL");
        var box = new DetectReviewAnnotation();
        box.setRecordId(1L); box.setClassName("split");
        box.setX1(240); box.setY1(140); box.setX2(480); box.setY2(300);
        when(batches.resolve("A")).thenReturn("A");
        when(records.selectList(any())).thenReturn(List.of(reviewed, empty, failed));
        when(annotations.selectList(any())).thenReturn(List.of(box));

        var facts = service.facts(new InspectionAnalysisService.Scope("A", null));
        assertEquals(3, facts.total());
        assertEquals(2, facts.photos().size());
        assertEquals(Map.of("split", 1), facts.defects());
        assertEquals(15.2, facts.photos().get(0).deduction(), 0.001);
        assertEquals(84.8, facts.photos().get(0).score(), 0.001);
        assertEquals(0.0, facts.photos().get(1).deduction(), 0.001);
        service.result(facts, false);
        verifyNoInteractions(model);
    }

    @Test
    void missingSelectedRecordsCannotBroadenTheScope() {
        assertThrows(BusinessException.class, () -> service.facts(new InspectionAnalysisService.Scope(null, List.of())));
        when(records.selectList(any())).thenReturn(List.of(record(2L, "SUCCESS")));
        assertThrows(BusinessException.class, () -> service.facts(new InspectionAnalysisService.Scope(null, List.of(2L, 3L))));
        verifyNoInteractions(model);
    }

    private static DetectRecord record(long id, String status) {
        var r = new DetectRecord();
        r.setId(id); r.setStatus(status); r.setImageName("photo-" + id);
        r.setImageWidth(800); r.setImageHeight(400); r.setQualityScore(100.0);
        return r;
    }
}
