package com.example.wooddetect.service.impl;

import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.common.DetectionStatus;
import com.example.wooddetect.config.FileUploadProperties;
import com.example.wooddetect.dto.ReviewAnnotationDTO;
import com.example.wooddetect.dto.ReviewSubmissionDTO;
import com.example.wooddetect.entity.DetectDetail;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.entity.DetectReviewAnnotation;
import com.example.wooddetect.mapper.DetectDetailMapper;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.example.wooddetect.mapper.DetectReviewAnnotationMapper;
import com.example.wooddetect.service.DetectService;
import com.example.wooddetect.service.FileStorageService;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.ModelVersionStatsVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.TransactionStatus;
import org.springframework.transaction.support.SimpleTransactionStatus;
import org.springframework.mock.web.MockHttpServletResponse;
import org.junit.jupiter.api.io.TempDir;

import java.io.ByteArrayInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ReviewServiceImplTest {

    private DetectRecordMapper recordMapper;
    private DetectDetailMapper detailMapper;
    private DetectReviewAnnotationMapper annotationMapper;
    private DetectService detectService;
    private ReviewServiceImpl service;
    private DetectRecord record;

    @BeforeEach
    void setUp() {
        recordMapper = mock(DetectRecordMapper.class);
        detailMapper = mock(DetectDetailMapper.class);
        annotationMapper = mock(DetectReviewAnnotationMapper.class);
        detectService = mock(DetectService.class);
        record = new DetectRecord();
        record.setId(7L);
        record.setStatus(DetectionStatus.SUCCESS);
        record.setImageWidth(1000);
        record.setImageHeight(500);
        when(recordMapper.selectById(7L)).thenReturn(record);
        when(detectService.getDetail(7L)).thenReturn(new DetectResponseVO());
        service = new ReviewServiceImpl(
                recordMapper, detailMapper, annotationMapper, detectService,
                new FileStorageService(new FileUploadProperties()), new ObjectMapper(), new NoOpTransactionManager());
    }

    @Test
    void correctReviewCopiesOriginalModelBoxes() {
        DetectDetail original = detail(11L, "split", 10, 20, 80, 100);
        when(detailMapper.selectList(any())).thenReturn(List.of(original));
        ReviewSubmissionDTO submission = new ReviewSubmissionDTO();
        submission.setReviewStatus("CORRECT");

        service.submitReview(7L, submission);

        ArgumentCaptor<DetectReviewAnnotation> annotation = ArgumentCaptor.forClass(DetectReviewAnnotation.class);
        verify(annotationMapper).insert(annotation.capture());
        assertEquals("split", annotation.getValue().getClassName());
        assertEquals("MODEL_CONFIRMED", annotation.getValue().getSourceType());
        assertEquals(11L, annotation.getValue().getOriginalDetailId());
        assertEquals("CORRECT", record.getReviewStatus());
    }

    @Test
    void correctedReviewMarksChangedAndAddedBoxes() {
        DetectDetail original = detail(11L, "split", 10, 20, 80, 100);
        when(detailMapper.selectList(any())).thenReturn(List.of(original));
        ReviewSubmissionDTO submission = new ReviewSubmissionDTO();
        submission.setReviewStatus("CORRECTED");
        submission.setAnnotations(List.of(
                annotation(11L, "dry_knot", 10, 20, 80, 100),
                annotation(null, "wave", 100, 100, 200, 200)
        ));

        service.submitReview(7L, submission);

        ArgumentCaptor<DetectReviewAnnotation> annotations = ArgumentCaptor.forClass(DetectReviewAnnotation.class);
        verify(annotationMapper, org.mockito.Mockito.times(2)).insert(annotations.capture());
        assertEquals(List.of("HUMAN_CORRECTED", "HUMAN_ADDED"),
                annotations.getAllValues().stream().map(DetectReviewAnnotation::getSourceType).toList());
    }

    @Test
    void rejectsAnnotationOutsideImage() {
        when(detailMapper.selectList(any())).thenReturn(List.of());
        ReviewSubmissionDTO submission = new ReviewSubmissionDTO();
        submission.setReviewStatus("CORRECTED");
        submission.setAnnotations(List.of(annotation(null, "split", 0, 0, 1001, 100)));

        assertThrows(BusinessException.class, () -> service.submitReview(7L, submission));
    }

    @Test
    void calculatesModelVersionReviewRatesAndChanges() {
        ModelVersionStatsVO current = stats("v2", 10L, 8L, 6L, 1L, 84.0);
        ModelVersionStatsVO previous = stats("v1", 10L, 5L, 3L, 1L, 80.0);
        when(recordMapper.selectModelVersionStats()).thenReturn(List.of(current, previous));

        List<ModelVersionStatsVO> result = service.getModelVersionStats();

        assertEquals(0.75, result.get(0).getConfirmationRate());
        assertEquals(0.15, result.get(0).getConfirmationRateChange());
        assertEquals(0.125, result.get(0).getCorrectionRate());
        assertEquals(-0.075, result.get(0).getCorrectionRateChange());
        assertEquals(4.0, result.get(0).getAverageQualityScoreChange());
        assertEquals(0.6, result.get(1).getConfirmationRate());
    }

    @Test
    void exportsReviewedAnnotationsAsYoloDataset(@TempDir Path tempDir) throws Exception {
        Path image = tempDir.resolve("sample.jpg");
        Files.write(image, new byte[]{1, 2, 3});
        DetectRecord exportRecord = new DetectRecord();
        exportRecord.setId(7L);
        exportRecord.setStatus(DetectionStatus.SUCCESS);
        exportRecord.setReviewStatus("CORRECTED");
        exportRecord.setImageName("sample.jpg");
        exportRecord.setImagePath(image.toString());
        exportRecord.setImageWidth(1000);
        exportRecord.setImageHeight(500);
        exportRecord.setModelVersion("best-abc123");
        DetectReviewAnnotation annotation = new DetectReviewAnnotation();
        annotation.setClassName("split");
        annotation.setX1(100);
        annotation.setY1(50);
        annotation.setX2(300);
        annotation.setY2(150);
        when(recordMapper.selectList(any())).thenReturn(List.of(exportRecord));
        when(annotationMapper.selectList(any())).thenReturn(List.of(annotation));
        FileUploadProperties properties = new FileUploadProperties();
        properties.setUploadPath(tempDir.toString());
        ReviewServiceImpl exportService = new ReviewServiceImpl(
                recordMapper, detailMapper, annotationMapper, detectService,
                new FileStorageService(properties), new ObjectMapper(), new NoOpTransactionManager());
        MockHttpServletResponse response = new MockHttpServletResponse();

        exportService.exportYoloDataset(null, null, null, response);

        Map<String, String> entries = unzipText(response.getContentAsByteArray());
        assertEquals("4 0.200000 0.200000 0.200000 0.200000\n",
                entries.get("wood-active-learning/labels/train/7_sample.txt"));
        assertEquals(true, entries.containsKey("wood-active-learning/images/train/7_sample.jpg"));
        assertEquals(true, entries.get("wood-active-learning/data.yaml").contains("4: split"));
        assertEquals(true, entries.get("wood-active-learning/manifest.json").contains("best-abc123"));
    }

    private DetectDetail detail(Long id, String className, int x1, int y1, int x2, int y2) {
        DetectDetail detail = new DetectDetail();
        detail.setId(id);
        detail.setClassName(className);
        detail.setConfidence(0.4);
        detail.setX1(x1);
        detail.setY1(y1);
        detail.setX2(x2);
        detail.setY2(y2);
        return detail;
    }

    private ReviewAnnotationDTO annotation(Long originalId, String className, int x1, int y1, int x2, int y2) {
        ReviewAnnotationDTO item = new ReviewAnnotationDTO();
        item.setOriginalDetailId(originalId);
        item.setClassName(className);
        item.setX1(x1);
        item.setY1(y1);
        item.setX2(x2);
        item.setY2(y2);
        return item;
    }

    private ModelVersionStatsVO stats(
            String version, long records, long reviewed, long correct, long corrected, double quality) {
        ModelVersionStatsVO stats = new ModelVersionStatsVO();
        stats.setModelVersion(version);
        stats.setRecordCount(records);
        stats.setReviewedCount(reviewed);
        stats.setCorrectCount(correct);
        stats.setCorrectedCount(corrected);
        stats.setIncorrectCount(reviewed - correct - corrected);
        stats.setAverageQualityScore(quality);
        stats.setAverageInferenceDurationMs(100.0);
        return stats;
    }

    private Map<String, String> unzipText(byte[] archive) throws Exception {
        Map<String, String> entries = new HashMap<>();
        try (ZipInputStream input = new ZipInputStream(new ByteArrayInputStream(archive))) {
            ZipEntry entry;
            while ((entry = input.getNextEntry()) != null) {
                entries.put(entry.getName(), new String(input.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
            }
        }
        return entries;
    }

    private static final class NoOpTransactionManager implements PlatformTransactionManager {
        @Override
        public TransactionStatus getTransaction(TransactionDefinition definition) {
            return new SimpleTransactionStatus();
        }

        @Override
        public void commit(TransactionStatus status) {
        }

        @Override
        public void rollback(TransactionStatus status) {
        }
    }
}
