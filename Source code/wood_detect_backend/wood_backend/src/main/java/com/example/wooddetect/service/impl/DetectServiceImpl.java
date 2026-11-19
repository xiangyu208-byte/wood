package com.example.wooddetect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.common.DetectionStatus;
import com.example.wooddetect.common.InferenceServiceException;
import com.example.wooddetect.config.FileUploadProperties;
import com.example.wooddetect.config.ActiveLearningProperties;
import com.example.wooddetect.dto.DetectionOptionsDTO;
import com.example.wooddetect.dto.PythonDetectResponseDTO;
import com.example.wooddetect.entity.DetectBatch;
import com.example.wooddetect.entity.DetectDetail;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.entity.DetectReviewAnnotation;
import com.example.wooddetect.mapper.DetectBatchMapper;
import com.example.wooddetect.mapper.DetectDetailMapper;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.example.wooddetect.mapper.DetectReviewAnnotationMapper;
import com.example.wooddetect.service.DetectService;
import com.example.wooddetect.service.FileStorageService;
import com.example.wooddetect.service.QualityScoringService;
import com.example.wooddetect.util.PythonDetectClient;
import com.example.wooddetect.vo.BatchTaskVO;
import com.example.wooddetect.vo.DetectDetailVO;
import com.example.wooddetect.vo.DetectHistoryVO;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.PageResultVO;
import com.example.wooddetect.vo.QualityDeductionVO;
import com.example.wooddetect.vo.ReviewAnnotationVO;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.task.TaskExecutor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
public class DetectServiceImpl implements DetectService {

    private static final Logger log = LoggerFactory.getLogger(DetectServiceImpl.class);
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> RECORD_STATUSES = Set.of(
            DetectionStatus.PENDING, DetectionStatus.PROCESSING, DetectionStatus.SUCCESS,
            DetectionStatus.FAIL, DetectionStatus.CANCELLED);
    private static final Set<String> SOURCE_TYPES = Set.of("UPLOAD", "CAMERA");
    private static final Set<String> MODEL_MODES = Set.of("FAST", "STANDARD", "ACCURATE");
    private static final Set<String> INFERENCE_PRECISIONS = Set.of("AUTO", "FP32", "FP16");
    private static final Set<String> QUALITY_GRADES = Set.of("A", "B", "C", "D");
    private static final Set<String> REVIEW_STATUSES = Set.of("UNREVIEWED", "CORRECT", "INCORRECT", "CORRECTED");
    private static final TypeReference<Map<String, Integer>> DEFECT_COUNTS_TYPE = new TypeReference<>() {};
    private static final TypeReference<List<QualityDeductionVO>> QUALITY_DEDUCTIONS_TYPE = new TypeReference<>() {};

    private final DetectRecordMapper detectRecordMapper;
    private final DetectDetailMapper detectDetailMapper;
    private final DetectBatchMapper detectBatchMapper;
    private final DetectReviewAnnotationMapper reviewAnnotationMapper;
    private final FileUploadProperties fileUploadProperties;
    private final ActiveLearningProperties activeLearningProperties;
    private final FileStorageService fileStorageService;
    private final PythonDetectClient pythonDetectClient;
    private final QualityScoringService qualityScoringService;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate transactionTemplate;
    private final TaskExecutor detectionTaskExecutor;

    public DetectServiceImpl(
            DetectRecordMapper detectRecordMapper,
            DetectDetailMapper detectDetailMapper,
            DetectBatchMapper detectBatchMapper,
            DetectReviewAnnotationMapper reviewAnnotationMapper,
            FileUploadProperties fileUploadProperties,
            ActiveLearningProperties activeLearningProperties,
            FileStorageService fileStorageService,
            PythonDetectClient pythonDetectClient,
            QualityScoringService qualityScoringService,
            ObjectMapper objectMapper,
            PlatformTransactionManager transactionManager,
            @Qualifier("detectionTaskExecutor") TaskExecutor detectionTaskExecutor
    ) {
        this.detectRecordMapper = detectRecordMapper;
        this.detectDetailMapper = detectDetailMapper;
        this.detectBatchMapper = detectBatchMapper;
        this.reviewAnnotationMapper = reviewAnnotationMapper;
        this.fileUploadProperties = fileUploadProperties;
        this.activeLearningProperties = activeLearningProperties;
        this.fileStorageService = fileStorageService;
        this.pythonDetectClient = pythonDetectClient;
        this.qualityScoringService = qualityScoringService;
        this.objectMapper = objectMapper;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.detectionTaskExecutor = detectionTaskExecutor;
    }

    @Override
    public DetectResponseVO uploadAndDetect(MultipartFile file, DetectionOptionsDTO rawOptions) {
        fileStorageService.validateImage(file);
        return processNewFile(file, null, "UPLOAD", normalizeOptions(rawOptions), true);
    }

    @Override
    public DetectResponseVO cameraUploadAndDetect(MultipartFile file, DetectionOptionsDTO rawOptions) {
        fileStorageService.validateImage(file);
        return processNewFile(file, "CAMERA_" + newBatchSuffix(), "CAMERA", normalizeOptions(rawOptions), true);
    }

    @Override
    public List<DetectResponseVO> batchUploadAndDetect(MultipartFile[] files, DetectionOptionsDTO rawOptions) {
        validateBatch(files);
        DetectionOptionsDTO options = normalizeOptions(rawOptions);
        String batchNo = "BATCH_" + newBatchSuffix();
        DetectBatch batch = createBatch(batchNo, files.length, DetectionStatus.BATCH_PROCESSING);
        List<DetectResponseVO> results = new ArrayList<>();

        for (MultipartFile file : files) {
            DetectResponseVO result = processNewFile(file, batchNo, "UPLOAD", options, false);
            results.add(result);
            updateBatchProgress(batch.getId(), DetectionStatus.SUCCESS.equals(result.getStatus()));
        }
        finalizeBatch(batch.getId());
        return results;
    }

    @Override
    public BatchTaskVO createAsyncBatch(MultipartFile[] files, DetectionOptionsDTO rawOptions) {
        validateBatch(files);
        DetectionOptionsDTO options = normalizeOptions(rawOptions);
        String batchNo = "ASYNC_" + newBatchSuffix();
        DetectBatch batch = createBatch(batchNo, files.length, DetectionStatus.BATCH_PENDING);
        List<Long> recordIds = new ArrayList<>();
        List<String> storedPaths = new ArrayList<>();

        try {
            for (MultipartFile file : files) {
                FileStorageService.StoredImage stored = fileStorageService.storeImage(file, "original");
                storedPaths.add(stored.absolutePath());
                DetectRecord record = createRecord(stored, batchNo, "UPLOAD", options, DetectionStatus.PENDING);
                recordIds.add(record.getId());
            }
        } catch (Exception e) {
            transactionTemplate.executeWithoutResult(status -> {
                if (!recordIds.isEmpty()) {
                    detectDetailMapper.delete(new QueryWrapper<DetectDetail>().in("record_id", recordIds));
                    detectRecordMapper.deleteBatchIds(recordIds);
                }
                detectBatchMapper.deleteById(batch.getId());
            });
            storedPaths.forEach(fileStorageService::deleteManagedFile);
            throw e;
        }

        try {
            detectionTaskExecutor.execute(() -> processQueuedBatch(batch.getId(), recordIds));
        } catch (RuntimeException e) {
            markBatchAndRecordsFailed(batch.getId(), recordIds, "批量任务无法进入执行队列");
            throw new BusinessException(HttpStatus.SERVICE_UNAVAILABLE, "批量任务队列已满，请稍后重试", e);
        }
        return getBatchStatus(batchNo);
    }

    @Override
    public BatchTaskVO getBatchStatus(String batchNo) {
        if (batchNo == null || batchNo.isBlank()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "批次号不能为空");
        }
        DetectBatch batch = detectBatchMapper.selectOne(
                new QueryWrapper<DetectBatch>().eq("batch_no", batchNo.trim()).last("LIMIT 1"));
        if (batch == null) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "批量任务不存在");
        }

        List<DetectRecord> records = detectRecordMapper.selectList(
                new QueryWrapper<DetectRecord>().eq("batch_no", batch.getBatchNo()).orderByAsc("id"));
        BatchTaskVO vo = new BatchTaskVO();
        vo.setBatchNo(batch.getBatchNo());
        vo.setTotalCount(batch.getTotalCount());
        vo.setProcessedCount(batch.getProcessedCount());
        vo.setSuccessCount(batch.getSuccessCount());
        vo.setFailCount(batch.getFailCount());
        vo.setCancelledCount(batch.getCancelledCount());
        vo.setStatus(batch.getStatus());
        vo.setCreateTime(batch.getCreateTime());
        vo.setUpdateTime(batch.getUpdateTime());
        vo.setItems(records.stream().map(record -> toResponseVO(record, List.of())).toList());
        return vo;
    }

    @Override
    public BatchTaskVO cancelBatch(String batchNo) {
        DetectBatch batch = requireBatch(batchNo);
        if (Set.of(DetectionStatus.BATCH_SUCCESS, DetectionStatus.BATCH_FAIL,
                DetectionStatus.BATCH_PARTIAL_FAIL, DetectionStatus.BATCH_CANCELLED).contains(batch.getStatus())) {
            if (DetectionStatus.BATCH_CANCELLED.equals(batch.getStatus())) {
                return getBatchStatus(batch.getBatchNo());
            }
            throw new BusinessException(HttpStatus.CONFLICT, "已结束的批量任务不能取消");
        }

        transactionTemplate.executeWithoutResult(status -> {
            List<DetectRecord> pending = detectRecordMapper.selectList(
                    new QueryWrapper<DetectRecord>()
                            .eq("batch_no", batch.getBatchNo())
                            .eq("status", DetectionStatus.PENDING));
            LocalDateTime now = LocalDateTime.now();
            for (DetectRecord record : pending) {
                record.setStatus(DetectionStatus.CANCELLED);
                record.setErrorMessage("用户取消任务");
                record.setUpdateTime(now);
                detectRecordMapper.updateById(record);
            }
            DetectBatch latest = detectBatchMapper.selectById(batch.getId());
            if (latest != null) {
                latest.setProcessedCount(Math.min(latest.getTotalCount(), latest.getProcessedCount() + pending.size()));
                latest.setCancelledCount(latest.getCancelledCount() + pending.size());
                latest.setStatus(DetectionStatus.BATCH_CANCELLED);
                latest.setUpdateTime(now);
                detectBatchMapper.updateById(latest);
            }
        });
        return getBatchStatus(batch.getBatchNo());
    }

    @Override
    public BatchTaskVO retryBatch(String batchNo) {
        DetectBatch batch = requireBatch(batchNo);
        long processingCount = detectRecordMapper.selectCount(
                new QueryWrapper<DetectRecord>()
                        .eq("batch_no", batch.getBatchNo())
                        .eq("status", DetectionStatus.PROCESSING));
        if (processingCount > 0 || DetectionStatus.BATCH_PENDING.equals(batch.getStatus())
                || DetectionStatus.BATCH_PROCESSING.equals(batch.getStatus())) {
            throw new BusinessException(HttpStatus.CONFLICT, "任务仍在处理中，请结束后再重试");
        }

        List<DetectRecord> retryRecords = detectRecordMapper.selectList(
                new QueryWrapper<DetectRecord>()
                        .eq("batch_no", batch.getBatchNo())
                        .in("status", List.of(DetectionStatus.FAIL, DetectionStatus.CANCELLED))
                        .orderByAsc("id"));
        if (retryRecords.isEmpty()) {
            throw new BusinessException(HttpStatus.CONFLICT, "当前批次没有可重试的失败或已取消项目");
        }

        List<Long> retryIds = retryRecords.stream().map(DetectRecord::getId).toList();
        transactionTemplate.executeWithoutResult(status -> {
            LocalDateTime now = LocalDateTime.now();
            for (DetectRecord record : retryRecords) {
                detectDetailMapper.delete(new QueryWrapper<DetectDetail>().eq("record_id", record.getId()));
                fileStorageService.deleteManagedFile(record.getResultImagePath());
                record.setResultImagePath(null);
                record.setResultImageUrl(null);
                record.setTotalCount(0);
                clearQualityAssessment(record);
                clearReviewMetadata(record);
                record.setStatus(DetectionStatus.PENDING);
                record.setErrorMessage(null);
                record.setUpdateTime(now);
                detectRecordMapper.updateById(record);
            }

            long successCount = detectRecordMapper.selectCount(
                    new QueryWrapper<DetectRecord>()
                            .eq("batch_no", batch.getBatchNo())
                            .eq("status", DetectionStatus.SUCCESS));
            DetectBatch latest = detectBatchMapper.selectById(batch.getId());
            latest.setProcessedCount((int) successCount);
            latest.setSuccessCount((int) successCount);
            latest.setFailCount(0);
            latest.setCancelledCount(0);
            latest.setStatus(DetectionStatus.BATCH_PENDING);
            latest.setUpdateTime(now);
            detectBatchMapper.updateById(latest);
        });

        try {
            detectionTaskExecutor.execute(() -> processQueuedBatch(batch.getId(), retryIds));
        } catch (RuntimeException e) {
            markBatchAndRecordsFailed(batch.getId(), retryIds, "批量任务无法进入执行队列");
            throw new BusinessException(HttpStatus.SERVICE_UNAVAILABLE, "批量任务队列已满，请稍后重试", e);
        }
        return getBatchStatus(batch.getBatchNo());
    }

    private void processQueuedBatch(Long batchId, List<Long> recordIds) {
        setBatchStatus(batchId, DetectionStatus.BATCH_PROCESSING);
        for (Long recordId : recordIds) {
            if (isBatchCancelled(batchId)) {
                break;
            }
            try {
                setRecordStatus(recordId, DetectionStatus.PROCESSING, null);
                DetectResponseVO result = processExistingRecord(recordId, false);
                updateBatchProgress(batchId, DetectionStatus.SUCCESS.equals(result.getStatus()));
            } catch (Exception e) {
                log.error("异步批量任务处理记录失败, recordId={}", recordId, e);
                markFailed(recordId, failureMessage(e));
                updateBatchProgress(batchId, false);
            }
        }
        if (!isBatchCancelled(batchId)) {
            finalizeBatch(batchId);
        }
    }

    private DetectResponseVO processNewFile(
            MultipartFile file,
            String batchNo,
            String sourceType,
            DetectionOptionsDTO options,
            boolean throwOnInferenceFailure) {
        FileStorageService.StoredImage stored = fileStorageService.storeImage(file, "original");
        DetectRecord record;
        try {
            record = createRecord(stored, batchNo, sourceType, options, DetectionStatus.PROCESSING);
        } catch (Exception e) {
            fileStorageService.deleteManagedFile(stored.absolutePath());
            throw e;
        }
        return processExistingRecord(record.getId(), throwOnInferenceFailure);
    }

    private DetectResponseVO processExistingRecord(Long recordId, boolean throwOnInferenceFailure) {
        DetectRecord record = requireRecord(recordId);
        PythonDetectResponseDTO response = null;
        try {
            response = pythonDetectClient.detect(record.getImagePath(), optionsFromRecord(record));
            validateInferenceResponse(response);
            persistSuccess(recordId, response);
            return getDetail(recordId);
        } catch (Exception e) {
            if (response != null) {
                fileStorageService.deleteManagedFile(response.getResultImagePath());
            }
            String message = failureMessage(e);
            markFailed(recordId, message);
            if (throwOnInferenceFailure) {
                if (e instanceof InferenceServiceException inferenceException) {
                    throw inferenceException;
                }
                throw new InferenceServiceException(message, e);
            }
            return getDetail(recordId);
        }
    }

    private void validateInferenceResponse(PythonDetectResponseDTO response) {
        if (response == null || !Boolean.TRUE.equals(response.getSuccess())) {
            throw new InferenceServiceException("推理服务返回失败状态");
        }
        Path resultPath = fileStorageService.resolveManagedFile(response.getResultImagePath());
        if (resultPath == null || !Files.isRegularFile(resultPath)) {
            throw new InferenceServiceException("推理结果图片不存在或路径不安全");
        }
    }

    private DetectRecord createRecord(
            FileStorageService.StoredImage stored,
            String batchNo,
            String sourceType,
            DetectionOptionsDTO options,
            String status) {
        DetectRecord record = new DetectRecord();
        LocalDateTime now = LocalDateTime.now();
        record.setImageName(stored.originalName());
        record.setImagePath(stored.absolutePath());
        record.setImageUrl(buildAccessUrl(stored.relativePath()));
        record.setTotalCount(0);
        record.setStatus(status);
        record.setBatchNo(batchNo);
        record.setSourceType(sourceType);
        record.setModelMode(options.getModelMode());
        record.setConfidenceThreshold(options.getConfidenceThreshold());
        record.setInferencePrecision(options.getInferencePrecision());
        record.setReviewNeeded(false);
        record.setReviewStatus("UNREVIEWED");
        record.setCreateTime(now);
        record.setUpdateTime(now);
        transactionTemplate.executeWithoutResult(transactionStatus -> detectRecordMapper.insert(record));
        if (record.getId() == null) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "创建检测记录失败");
        }
        return record;
    }

    private void persistSuccess(Long recordId, PythonDetectResponseDTO response) {
        QualityScoringService.Assessment quality = qualityScoringService.assess(
                qualityBoxes(response.getDetails()), response.getImageWidth(), response.getImageHeight());
        transactionTemplate.executeWithoutResult(status -> {
            DetectRecord record = requireRecord(recordId);
            if (!DetectionStatus.PROCESSING.equals(record.getStatus())) {
                throw new IllegalStateException("非法状态转换：" + record.getStatus() + " -> SUCCESS");
            }
            record.setResultImagePath(response.getResultImagePath());
            record.setResultImageUrl(response.getResultImageUrl());
            record.setTotalCount(response.getTotalCount() == null ? 0 : response.getTotalCount());
            record.setActualMode(response.getActualMode());
            record.setDecisionReason(response.getDecisionReason());
            record.setInferenceDurationMs(response.getInferenceDurationMs());
            record.setTileCount(response.getTileCount() == null ? 1 : response.getTileCount());
            record.setImageWidth(response.getImageWidth());
            record.setImageHeight(response.getImageHeight());
            applyReviewMetadata(record, response);
            record.setQualityScore(quality.score());
            record.setQualityGrade(quality.grade());
            record.setDefectAreaRatio(quality.defectAreaRatio());
            record.setMaxDefectAreaRatio(quality.maxDefectAreaRatio());
            record.setDefectCountsJson(writeJson(quality.defectCounts()));
            record.setQualityDeductionsJson(writeJson(quality.deductions()));
            record.setQualityRuleVersion(quality.ruleVersion());
            record.setQualityDisclaimer(quality.disclaimer());
            record.setStatus(DetectionStatus.SUCCESS);
            record.setErrorMessage(null);
            record.setUpdateTime(LocalDateTime.now());
            detectRecordMapper.updateById(record);
            saveDetectDetails(recordId, response.getDetails());
        });
    }

    private List<QualityScoringService.QualityBox> qualityBoxes(
            List<PythonDetectResponseDTO.DetectItemDTO> details) {
        if (details == null) return List.of();
        return details.stream().map(item -> new QualityScoringService.QualityBox(
                item.getClassName(),
                item.getX1() == null ? 0 : item.getX1(),
                item.getY1() == null ? 0 : item.getY1(),
                item.getX2() == null ? 0 : item.getX2(),
                item.getY2() == null ? 0 : item.getY2()
        )).toList();
    }

    private void clearQualityAssessment(DetectRecord record) {
        record.setQualityScore(null);
        record.setQualityGrade(null);
        record.setDefectAreaRatio(null);
        record.setMaxDefectAreaRatio(null);
        record.setDefectCountsJson(null);
        record.setQualityDeductionsJson(null);
        record.setQualityRuleVersion(null);
        record.setQualityDisclaimer(null);
    }

    private void applyReviewMetadata(DetectRecord record, PythonDetectResponseDTO response) {
        List<PythonDetectResponseDTO.DetectItemDTO> details = response.getDetails() == null
                ? List.of() : response.getDetails();
        List<Double> modelConfidences = details.stream()
                .filter(item -> item != null && !"suspected_anomaly".equals(item.getClassName()))
                .map(PythonDetectResponseDTO.DetectItemDTO::getConfidence)
                .filter(java.util.Objects::nonNull)
                .toList();
        Double minConfidence = modelConfidences.stream().min(Double::compareTo).orElse(null);
        boolean suspected = details.stream().anyMatch(
                item -> item != null && "suspected_anomaly".equals(item.getClassName()));
        boolean lowConfidence = minConfidence != null
                && minConfidence < activeLearningProperties.getLowConfidenceThreshold();

        record.setModelVersion(hasText(response.getModelVersion()) ? response.getModelVersion().trim() : "unknown");
        record.setMinConfidence(minConfidence);
        record.setReviewNeeded(suspected || lowConfidence);
        record.setReviewReason(suspected ? "SUSPECTED_ANOMALY" : lowConfidence ? "LOW_CONFIDENCE" : null);
        record.setReviewStatus("UNREVIEWED");
        record.setReviewComment(null);
        record.setReviewedAt(null);
    }

    private void clearReviewMetadata(DetectRecord record) {
        record.setModelVersion(null);
        record.setMinConfidence(null);
        record.setReviewNeeded(false);
        record.setReviewReason(null);
        record.setReviewStatus("UNREVIEWED");
        record.setReviewComment(null);
        record.setReviewedAt(null);
        reviewAnnotationMapper.delete(new QueryWrapper<DetectReviewAnnotation>().eq("record_id", record.getId()));
    }

    private void markFailed(Long recordId, String message) {
        try {
            transactionTemplate.executeWithoutResult(status -> {
                DetectRecord record = requireRecord(recordId);
                if (DetectionStatus.SUCCESS.equals(record.getStatus())) {
                    return;
                }
                record.setStatus(DetectionStatus.FAIL);
                record.setErrorMessage(truncate(message, 2000));
                record.setUpdateTime(LocalDateTime.now());
                detectRecordMapper.updateById(record);
            });
        } catch (Exception e) {
            log.error("更新失败状态异常, recordId={}", recordId, e);
            throw e;
        }
    }

    private void setRecordStatus(Long recordId, String status, String errorMessage) {
        transactionTemplate.executeWithoutResult(transactionStatus -> {
            DetectRecord record = requireRecord(recordId);
            record.setStatus(status);
            record.setErrorMessage(errorMessage);
            record.setUpdateTime(LocalDateTime.now());
            detectRecordMapper.updateById(record);
        });
    }

    private void saveDetectDetails(Long recordId, List<PythonDetectResponseDTO.DetectItemDTO> details) {
        if (details == null) {
            return;
        }
        for (PythonDetectResponseDTO.DetectItemDTO item : details) {
            DetectDetail detail = new DetectDetail();
            detail.setRecordId(recordId);
            detail.setClassName(item.getClassName());
            detail.setConfidence(item.getConfidence());
            detail.setX1(item.getX1());
            detail.setY1(item.getY1());
            detail.setX2(item.getX2());
            detail.setY2(item.getY2());
            detail.setCreateTime(LocalDateTime.now());
            detectDetailMapper.insert(detail);
        }
    }

    @Override
    public PageResultVO<DetectHistoryVO> getHistory(
            Integer page, Integer size, String imageName, String status, String batchNo,
            String sourceType, String hasDefect, String qualityGrade,
            Double minQualityScore, Double maxQualityScore, String modelVersion,
            String reviewStatus, String reviewQueue, String startTime, String endTime) {
        int safePage = page == null ? 1 : page;
        int safeSize = size == null ? 10 : size;
        if (safePage < 1 || safeSize < 1 || safeSize > 100) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "页码必须大于 0，每页数量必须在 1 到 100 之间");
        }

        QueryWrapper<DetectRecord> wrapper = buildHistoryQueryWrapper(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime);
        Page<DetectRecord> resultPage = detectRecordMapper.selectPage(new Page<>(safePage, safeSize), wrapper);

        PageResultVO<DetectHistoryVO> result = new PageResultVO<>();
        result.setRecords(resultPage.getRecords().stream().map(this::toHistoryVO).toList());
        result.setTotal(resultPage.getTotal());
        result.setPage(safePage);
        result.setSize(safeSize);
        return result;
    }

    @Override
    public DetectResponseVO getDetail(Long id) {
        DetectRecord record = requireRecord(id);
        List<DetectDetail> details = detectDetailMapper.selectList(
                new QueryWrapper<DetectDetail>().eq("record_id", id).orderByAsc("id"));
        DetectResponseVO response = toResponseVO(record, details);
        response.setReviewAnnotations(reviewAnnotationMapper.selectList(
                new QueryWrapper<DetectReviewAnnotation>().eq("record_id", id).orderByAsc("id"))
                .stream().map(this::toReviewAnnotationVO).toList());
        return response;
    }

    @Override
    public void deleteRecord(Long id) {
        deleteRecordsByIds(List.of(id), true);
    }

    @Override
    public void batchDeleteRecords(List<Long> ids) {
        if (ids == null || ids.isEmpty()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "要删除的记录 ID 不能为空");
        }
        List<Long> normalized = ids.stream().filter(java.util.Objects::nonNull).distinct().toList();
        if (normalized.isEmpty()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "要删除的记录 ID 不能为空");
        }
        deleteRecordsByIds(normalized, true);
    }

    @Override
    public void deleteRecordsByCondition(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String qualityGrade, Double minQualityScore, Double maxQualityScore,
            String modelVersion, String reviewStatus, String reviewQueue, String startTime, String endTime) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime);
        if (records.isEmpty()) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "没有符合条件的记录可删除");
        }
        deleteRecords(records);
    }

    private void deleteRecordsByIds(List<Long> ids, boolean requireAll) {
        List<DetectRecord> records = detectRecordMapper.selectBatchIds(ids);
        if (records.isEmpty() || (requireAll && records.size() != new HashSet<>(ids).size())) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "部分或全部检测记录不存在");
        }
        deleteRecords(records);
    }

    private void deleteRecords(List<DetectRecord> records) {
        List<Long> ids = records.stream().map(DetectRecord::getId).toList();
        List<String> files = records.stream()
                .flatMap(record -> java.util.stream.Stream.of(record.getImagePath(), record.getResultImagePath()))
                .toList();
        List<FileStorageService.StagedDeletion> staged = fileStorageService.stageForDeletion(files);
        try {
            transactionTemplate.executeWithoutResult(status -> {
                detectDetailMapper.delete(new QueryWrapper<DetectDetail>().in("record_id", ids));
                detectRecordMapper.deleteBatchIds(ids);
            });
            fileStorageService.finalizeDeletion(staged);
        } catch (Exception e) {
            fileStorageService.restore(staged);
            throw e;
        }
    }

    @Override
    public void exportHistoryCsv(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String qualityGrade, Double minQualityScore, Double maxQualityScore,
            String modelVersion, String reviewStatus, String reviewQueue,
            String startTime, String endTime, HttpServletResponse response) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime);
        response.setContentType("text/csv;charset=UTF-8");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader("Content-Disposition", "attachment; filename=detect_history.csv");
        try (PrintWriter writer = response.getWriter()) {
            writer.write('\uFEFF');
            writer.println("记录ID,批次号,来源类型,图片名称,原图URL,结果图URL,缺陷数,状态,失败原因,请求模式,实际模式,模式原因,推理精度,推理耗时毫秒,推理区域数,图片尺寸,质量分,质量等级,缺陷覆盖率,最大缺陷面积率,各类别数量,扣分明细,评分规则版本,评价说明,模型版本,最低置信度,自动复核标记,复核原因,人工复核状态,复核备注,复核时间,创建时间");
            for (DetectRecord record : records) {
                writer.println(String.join(",", List.of(
                        String.valueOf(record.getId()), safeCsv(record.getBatchNo()), safeCsv(record.getSourceType()),
                        safeCsv(record.getImageName()), safeCsv(record.getImageUrl()), safeCsv(record.getResultImageUrl()),
                        String.valueOf(record.getTotalCount() == null ? 0 : record.getTotalCount()),
                        safeCsv(record.getStatus()), safeCsv(record.getErrorMessage()), safeCsv(record.getModelMode()),
                        safeCsv(record.getActualMode()), safeCsv(record.getDecisionReason()), safeCsv(record.getInferencePrecision()),
                        numberText(record.getInferenceDurationMs()), numberText(record.getTileCount()), safeCsv(imageSize(record)),
                        numberText(record.getQualityScore()), safeCsv(record.getQualityGrade()),
                        ratioPercentText(record.getDefectAreaRatio()), ratioPercentText(record.getMaxDefectAreaRatio()),
                        safeCsv(record.getDefectCountsJson()), safeCsv(record.getQualityDeductionsJson()),
                        safeCsv(record.getQualityRuleVersion()), safeCsv(record.getQualityDisclaimer()),
                        safeCsv(record.getModelVersion()), numberText(record.getMinConfidence()),
                        Boolean.TRUE.equals(record.getReviewNeeded()) ? "YES" : "NO",
                        safeCsv(record.getReviewReason()), safeCsv(record.getReviewStatus()),
                        safeCsv(record.getReviewComment()),
                        record.getReviewedAt() == null ? "" : record.getReviewedAt().toString(),
                        record.getCreateTime() == null ? "" : record.getCreateTime().toString()
                )));
            }
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "导出 CSV 失败", e);
        }
    }

    @Override
    public void exportHistoryExcel(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String qualityGrade, Double minQualityScore, Double maxQualityScore,
            String modelVersion, String reviewStatus, String reviewQueue,
            String startTime, String endTime, HttpServletResponse response) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime);
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setHeader("Content-Disposition", "attachment; filename=detect_history.xlsx");
        try (XSSFWorkbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("历史记录");
            String[] headers = {"记录ID", "批次号", "来源类型", "图片名称", "原图URL", "结果图URL", "缺陷数", "状态", "失败原因", "请求模式", "实际模式", "模式原因", "推理精度", "推理耗时毫秒", "推理区域数", "图片尺寸", "质量分", "质量等级", "缺陷覆盖率", "最大缺陷面积率", "各类别数量", "扣分明细", "评分规则版本", "评价说明", "模型版本", "最低置信度", "自动复核标记", "复核原因", "人工复核状态", "复核备注", "复核时间", "创建时间"};
            Row header = sheet.createRow(0);
            for (int i = 0; i < headers.length; i++) {
                header.createCell(i).setCellValue(headers[i]);
            }
            int rowNumber = 1;
            for (DetectRecord record : records) {
                Row row = sheet.createRow(rowNumber++);
                row.createCell(0).setCellValue(record.getId());
                row.createCell(1).setCellValue(nullToEmpty(record.getBatchNo()));
                row.createCell(2).setCellValue(nullToEmpty(record.getSourceType()));
                row.createCell(3).setCellValue(nullToEmpty(record.getImageName()));
                row.createCell(4).setCellValue(nullToEmpty(record.getImageUrl()));
                row.createCell(5).setCellValue(nullToEmpty(record.getResultImageUrl()));
                row.createCell(6).setCellValue(record.getTotalCount() == null ? 0 : record.getTotalCount());
                row.createCell(7).setCellValue(nullToEmpty(record.getStatus()));
                row.createCell(8).setCellValue(nullToEmpty(record.getErrorMessage()));
                row.createCell(9).setCellValue(nullToEmpty(record.getModelMode()));
                row.createCell(10).setCellValue(nullToEmpty(record.getActualMode()));
                row.createCell(11).setCellValue(nullToEmpty(record.getDecisionReason()));
                row.createCell(12).setCellValue(nullToEmpty(record.getInferencePrecision()));
                row.createCell(13).setCellValue(record.getInferenceDurationMs() == null ? 0 : record.getInferenceDurationMs());
                row.createCell(14).setCellValue(record.getTileCount() == null ? 0 : record.getTileCount());
                row.createCell(15).setCellValue(imageSize(record));
                if (record.getQualityScore() == null) row.createCell(16).setCellValue("");
                else row.createCell(16).setCellValue(record.getQualityScore());
                row.createCell(17).setCellValue(nullToEmpty(record.getQualityGrade()));
                row.createCell(18).setCellValue(ratioPercentText(record.getDefectAreaRatio()));
                row.createCell(19).setCellValue(ratioPercentText(record.getMaxDefectAreaRatio()));
                row.createCell(20).setCellValue(nullToEmpty(record.getDefectCountsJson()));
                row.createCell(21).setCellValue(nullToEmpty(record.getQualityDeductionsJson()));
                row.createCell(22).setCellValue(nullToEmpty(record.getQualityRuleVersion()));
                row.createCell(23).setCellValue(nullToEmpty(record.getQualityDisclaimer()));
                row.createCell(24).setCellValue(nullToEmpty(record.getModelVersion()));
                if (record.getMinConfidence() == null) row.createCell(25).setCellValue("");
                else row.createCell(25).setCellValue(record.getMinConfidence());
                row.createCell(26).setCellValue(Boolean.TRUE.equals(record.getReviewNeeded()) ? "YES" : "NO");
                row.createCell(27).setCellValue(nullToEmpty(record.getReviewReason()));
                row.createCell(28).setCellValue(nullToEmpty(record.getReviewStatus()));
                row.createCell(29).setCellValue(nullToEmpty(record.getReviewComment()));
                row.createCell(30).setCellValue(record.getReviewedAt() == null ? "" : record.getReviewedAt().toString());
                row.createCell(31).setCellValue(record.getCreateTime() == null ? "" : record.getCreateTime().toString());
            }
            for (int i = 0; i < headers.length; i++) {
                sheet.autoSizeColumn(i);
            }
            workbook.write(response.getOutputStream());
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "导出 Excel 失败", e);
        }
    }

    @Override
    public void exportHistoryImagesZip(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String qualityGrade, Double minQualityScore, Double maxQualityScore,
            String modelVersion, String reviewStatus, String reviewQueue,
            String startTime, String endTime, HttpServletResponse response) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime);
        if (records.isEmpty()) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "没有符合条件的图片可下载");
        }
        response.setContentType("application/zip");
        response.setHeader("Content-Disposition", "attachment; filename=detect_images.zip");
        try (ZipOutputStream output = new ZipOutputStream(response.getOutputStream())) {
            for (DetectRecord record : records) {
                String name = record.getId() + "_" + safeFileName(record.getImageName());
                addFileToZip(output, record.getImagePath(), "original/" + name);
                addFileToZip(output, record.getResultImagePath(), "result/" + name);
            }
            output.finish();
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "导出图片 ZIP 失败", e);
        }
    }

    private List<DetectRecord> listHistoryRecords(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String qualityGrade, Double minQualityScore, Double maxQualityScore,
            String modelVersion, String reviewStatus, String reviewQueue, String startTime, String endTime) {
        return detectRecordMapper.selectList(buildHistoryQueryWrapper(
                imageName, status, batchNo, sourceType, hasDefect,
                qualityGrade, minQualityScore, maxQualityScore,
                modelVersion, reviewStatus, reviewQueue, startTime, endTime));
    }

    private QueryWrapper<DetectRecord> buildHistoryQueryWrapper(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String qualityGrade, Double minQualityScore, Double maxQualityScore,
            String modelVersion, String reviewStatus, String reviewQueue, String startTime, String endTime) {
        QueryWrapper<DetectRecord> wrapper = new QueryWrapper<>();
        if (hasText(imageName)) {
            wrapper.like("image_name", imageName.trim());
        }
        if (hasText(status)) {
            String normalized = status.trim().toUpperCase();
            if (!RECORD_STATUSES.contains(normalized)) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "无效的任务状态：" + status);
            }
            wrapper.eq("status", normalized);
        }
        if (hasText(batchNo)) {
            wrapper.like("batch_no", batchNo.trim());
        }
        if (hasText(sourceType)) {
            String normalized = sourceType.trim().toUpperCase();
            if (!SOURCE_TYPES.contains(normalized)) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "无效的来源类型：" + sourceType);
            }
            wrapper.eq("source_type", normalized);
        }
        if (hasText(hasDefect)) {
            if ("YES".equalsIgnoreCase(hasDefect.trim())) {
                wrapper.gt("total_count", 0);
            } else if ("NO".equalsIgnoreCase(hasDefect.trim())) {
                wrapper.eq("total_count", 0);
            } else {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "hasDefect 仅支持 YES 或 NO");
            }
        }
        if (hasText(qualityGrade)) {
            String normalized = qualityGrade.trim().toUpperCase();
            if (!QUALITY_GRADES.contains(normalized)) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "qualityGrade 仅支持 A、B、C 或 D");
            }
            wrapper.eq("quality_grade", normalized);
        }
        validateQualityScoreRange(minQualityScore, maxQualityScore);
        if (minQualityScore != null) wrapper.ge("quality_score", minQualityScore);
        if (maxQualityScore != null) wrapper.le("quality_score", maxQualityScore);
        if (hasText(modelVersion)) wrapper.eq("model_version", modelVersion.trim());
        if (hasText(reviewStatus)) {
            String normalized = reviewStatus.trim().toUpperCase();
            if (!REVIEW_STATUSES.contains(normalized)) {
                throw new BusinessException(HttpStatus.BAD_REQUEST,
                        "reviewStatus 仅支持 UNREVIEWED、CORRECT、INCORRECT 或 CORRECTED");
            }
            wrapper.eq("review_status", normalized);
        }
        if (hasText(reviewQueue)) {
            if ("YES".equalsIgnoreCase(reviewQueue.trim())) {
                wrapper.eq("review_needed", true).eq("review_status", "UNREVIEWED");
            } else if ("NO".equalsIgnoreCase(reviewQueue.trim())) {
                wrapper.and(item -> item.eq("review_needed", false).or().ne("review_status", "UNREVIEWED"));
            } else {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "reviewQueue 仅支持 YES 或 NO");
            }
        }

        LocalDateTime start = parseDateTime(startTime, "开始时间");
        LocalDateTime end = parseDateTime(endTime, "结束时间");
        if (start != null && end != null && start.isAfter(end)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "开始时间不能晚于结束时间");
        }
        if (start != null) {
            wrapper.ge("create_time", start);
        }
        if (end != null) {
            wrapper.le("create_time", end);
        }
        return wrapper.orderByDesc("create_time").orderByDesc("id");
    }

    private DetectBatch createBatch(String batchNo, int total, String status) {
        DetectBatch batch = new DetectBatch();
        LocalDateTime now = LocalDateTime.now();
        batch.setBatchNo(batchNo);
        batch.setTotalCount(total);
        batch.setProcessedCount(0);
        batch.setSuccessCount(0);
        batch.setFailCount(0);
        batch.setCancelledCount(0);
        batch.setStatus(status);
        batch.setCreateTime(now);
        batch.setUpdateTime(now);
        transactionTemplate.executeWithoutResult(transactionStatus -> detectBatchMapper.insert(batch));
        return batch;
    }

    private void updateBatchProgress(Long batchId, boolean success) {
        transactionTemplate.executeWithoutResult(status -> {
            DetectBatch batch = detectBatchMapper.selectById(batchId);
            if (batch == null) {
                return;
            }
            batch.setProcessedCount(batch.getProcessedCount() + 1);
            if (success) {
                batch.setSuccessCount(batch.getSuccessCount() + 1);
            } else {
                batch.setFailCount(batch.getFailCount() + 1);
            }
            batch.setUpdateTime(LocalDateTime.now());
            detectBatchMapper.updateById(batch);
        });
    }

    private void finalizeBatch(Long batchId) {
        transactionTemplate.executeWithoutResult(status -> {
            DetectBatch batch = detectBatchMapper.selectById(batchId);
            if (batch == null) {
                return;
            }
            if (DetectionStatus.BATCH_CANCELLED.equals(batch.getStatus())) {
                return;
            }
            if (batch.getSuccessCount() == batch.getTotalCount()) {
                batch.setStatus(DetectionStatus.BATCH_SUCCESS);
            } else if (batch.getFailCount() == batch.getTotalCount()) {
                batch.setStatus(DetectionStatus.BATCH_FAIL);
            } else {
                batch.setStatus(DetectionStatus.BATCH_PARTIAL_FAIL);
            }
            batch.setUpdateTime(LocalDateTime.now());
            detectBatchMapper.updateById(batch);
        });
    }

    private void setBatchStatus(Long batchId, String status) {
        transactionTemplate.executeWithoutResult(transactionStatus -> {
            DetectBatch batch = detectBatchMapper.selectById(batchId);
            if (batch != null) {
                if (DetectionStatus.BATCH_CANCELLED.equals(batch.getStatus())
                        && !DetectionStatus.BATCH_CANCELLED.equals(status)) {
                    return;
                }
                batch.setStatus(status);
                batch.setUpdateTime(LocalDateTime.now());
                detectBatchMapper.updateById(batch);
            }
        });
    }

    private void markBatchAndRecordsFailed(Long batchId, List<Long> recordIds, String message) {
        transactionTemplate.executeWithoutResult(status -> {
            for (Long recordId : recordIds) {
                DetectRecord record = detectRecordMapper.selectById(recordId);
                if (record != null) {
                    record.setStatus(DetectionStatus.FAIL);
                    record.setErrorMessage(message);
                    record.setUpdateTime(LocalDateTime.now());
                    detectRecordMapper.updateById(record);
                }
            }
            DetectBatch batch = detectBatchMapper.selectById(batchId);
            if (batch != null) {
                long successCount = detectRecordMapper.selectCount(
                        new QueryWrapper<DetectRecord>()
                                .eq("batch_no", batch.getBatchNo())
                                .eq("status", DetectionStatus.SUCCESS));
                long failCount = detectRecordMapper.selectCount(
                        new QueryWrapper<DetectRecord>()
                                .eq("batch_no", batch.getBatchNo())
                                .eq("status", DetectionStatus.FAIL));
                long cancelledCount = detectRecordMapper.selectCount(
                        new QueryWrapper<DetectRecord>()
                                .eq("batch_no", batch.getBatchNo())
                                .eq("status", DetectionStatus.CANCELLED));
                batch.setSuccessCount((int) successCount);
                batch.setFailCount((int) failCount);
                batch.setCancelledCount((int) cancelledCount);
                batch.setProcessedCount((int) (successCount + failCount + cancelledCount));
                batch.setStatus(successCount > 0
                        ? DetectionStatus.BATCH_PARTIAL_FAIL
                        : DetectionStatus.BATCH_FAIL);
                batch.setUpdateTime(LocalDateTime.now());
                detectBatchMapper.updateById(batch);
            }
        });
    }

    private void validateBatch(MultipartFile[] files) {
        if (files == null || files.length == 0) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "上传文件不能为空");
        }
        if (files.length > fileUploadProperties.getMaxBatchSize()) {
            throw new BusinessException(HttpStatus.PAYLOAD_TOO_LARGE,
                    "单次批量上传最多支持 " + fileUploadProperties.getMaxBatchSize() + " 张图片");
        }
        for (MultipartFile file : files) {
            fileStorageService.validateImage(file);
        }
    }

    private DetectionOptionsDTO normalizeOptions(DetectionOptionsDTO rawOptions) {
        String mode = rawOptions == null || !hasText(rawOptions.getModelMode())
                ? "STANDARD" : rawOptions.getModelMode().trim().toUpperCase();
        String precision = rawOptions == null || !hasText(rawOptions.getInferencePrecision())
                ? "AUTO" : rawOptions.getInferencePrecision().trim().toUpperCase();
        Double confidence = rawOptions == null || rawOptions.getConfidenceThreshold() == null
                ? 0.25 : rawOptions.getConfidenceThreshold();

        if (!MODEL_MODES.contains(mode)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "modelMode 仅支持 FAST、STANDARD 或 ACCURATE");
        }
        if (!INFERENCE_PRECISIONS.contains(precision)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "precision 仅支持 AUTO、FP32 或 FP16");
        }
        if (!Double.isFinite(confidence) || confidence < 0.05 || confidence > 0.95) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "confidenceThreshold 必须在 0.05 到 0.95 之间");
        }
        return new DetectionOptionsDTO(mode, confidence, precision);
    }

    private DetectionOptionsDTO optionsFromRecord(DetectRecord record) {
        return normalizeOptions(new DetectionOptionsDTO(
                record.getModelMode(), record.getConfidenceThreshold(), record.getInferencePrecision()));
    }

    private DetectBatch requireBatch(String batchNo) {
        if (!hasText(batchNo)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "批次号不能为空");
        }
        DetectBatch batch = detectBatchMapper.selectOne(
                new QueryWrapper<DetectBatch>().eq("batch_no", batchNo.trim()).last("LIMIT 1"));
        if (batch == null) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "批量任务不存在");
        }
        return batch;
    }

    private boolean isBatchCancelled(Long batchId) {
        DetectBatch batch = detectBatchMapper.selectById(batchId);
        return batch != null && DetectionStatus.BATCH_CANCELLED.equals(batch.getStatus());
    }

    private DetectRecord requireRecord(Long id) {
        if (id == null || id <= 0) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "记录 ID 不合法");
        }
        DetectRecord record = detectRecordMapper.selectById(id);
        if (record == null) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "检测记录不存在，ID=" + id);
        }
        return record;
    }

    private DetectHistoryVO toHistoryVO(DetectRecord record) {
        DetectHistoryVO vo = new DetectHistoryVO();
        vo.setRecordId(record.getId());
        vo.setBatchNo(record.getBatchNo());
        vo.setSourceType(record.getSourceType());
        vo.setModelMode(record.getModelMode());
        vo.setActualMode(record.getActualMode());
        vo.setDecisionReason(record.getDecisionReason());
        vo.setConfidenceThreshold(record.getConfidenceThreshold());
        vo.setInferencePrecision(record.getInferencePrecision());
        vo.setModelVersion(record.getModelVersion());
        vo.setMinConfidence(record.getMinConfidence());
        vo.setReviewNeeded(record.getReviewNeeded());
        vo.setReviewReason(record.getReviewReason());
        vo.setReviewStatus(record.getReviewStatus());
        vo.setReviewComment(record.getReviewComment());
        vo.setReviewedAt(record.getReviewedAt());
        vo.setInferenceDurationMs(record.getInferenceDurationMs());
        vo.setTileCount(record.getTileCount());
        vo.setImageWidth(record.getImageWidth());
        vo.setImageHeight(record.getImageHeight());
        vo.setQualityScore(record.getQualityScore());
        vo.setQualityGrade(record.getQualityGrade());
        vo.setDefectAreaRatio(record.getDefectAreaRatio());
        vo.setMaxDefectAreaRatio(record.getMaxDefectAreaRatio());
        vo.setQualityRuleVersion(record.getQualityRuleVersion());
        vo.setImageName(record.getImageName());
        vo.setImageUrl(record.getImageUrl());
        vo.setResultImageUrl(record.getResultImageUrl());
        vo.setTotalCount(record.getTotalCount());
        vo.setStatus(record.getStatus());
        vo.setErrorMessage(record.getErrorMessage());
        vo.setCreateTime(record.getCreateTime());
        return vo;
    }

    private DetectResponseVO toResponseVO(DetectRecord record, List<DetectDetail> details) {
        DetectResponseVO vo = new DetectResponseVO();
        vo.setRecordId(record.getId());
        vo.setBatchNo(record.getBatchNo());
        vo.setImageName(record.getImageName());
        vo.setImageUrl(record.getImageUrl());
        vo.setResultImageUrl(record.getResultImageUrl());
        vo.setTotalCount(record.getTotalCount());
        vo.setStatus(record.getStatus());
        vo.setErrorMessage(record.getErrorMessage());
        vo.setSourceType(record.getSourceType());
        vo.setModelMode(record.getModelMode());
        vo.setActualMode(record.getActualMode());
        vo.setDecisionReason(record.getDecisionReason());
        vo.setConfidenceThreshold(record.getConfidenceThreshold());
        vo.setInferencePrecision(record.getInferencePrecision());
        vo.setModelVersion(record.getModelVersion());
        vo.setMinConfidence(record.getMinConfidence());
        vo.setReviewNeeded(record.getReviewNeeded());
        vo.setReviewReason(record.getReviewReason());
        vo.setReviewStatus(record.getReviewStatus());
        vo.setReviewComment(record.getReviewComment());
        vo.setReviewedAt(record.getReviewedAt());
        vo.setReviewAnnotations(List.of());
        vo.setInferenceDurationMs(record.getInferenceDurationMs());
        vo.setTileCount(record.getTileCount());
        vo.setImageWidth(record.getImageWidth());
        vo.setImageHeight(record.getImageHeight());
        vo.setQualityScore(record.getQualityScore());
        vo.setQualityGrade(record.getQualityGrade());
        vo.setDefectAreaRatio(record.getDefectAreaRatio());
        vo.setMaxDefectAreaRatio(record.getMaxDefectAreaRatio());
        vo.setDefectCounts(readJson(record.getDefectCountsJson(), DEFECT_COUNTS_TYPE, Map.of()));
        vo.setQualityDeductions(readJson(record.getQualityDeductionsJson(), QUALITY_DEDUCTIONS_TYPE, List.of()));
        vo.setQualityRuleVersion(record.getQualityRuleVersion());
        vo.setQualityDisclaimer(record.getQualityDisclaimer());
        vo.setCreateTime(record.getCreateTime());
        vo.setDetails(details.stream().map(this::toDetailVO).toList());
        return vo;
    }

    private DetectDetailVO toDetailVO(DetectDetail detail) {
        DetectDetailVO vo = new DetectDetailVO();
        vo.setDetailId(detail.getId());
        vo.setClassName(detail.getClassName());
        vo.setConfidence(detail.getConfidence());
        vo.setX1(detail.getX1());
        vo.setY1(detail.getY1());
        vo.setX2(detail.getX2());
        vo.setY2(detail.getY2());
        return vo;
    }

    private ReviewAnnotationVO toReviewAnnotationVO(DetectReviewAnnotation annotation) {
        ReviewAnnotationVO vo = new ReviewAnnotationVO();
        vo.setId(annotation.getId());
        vo.setOriginalDetailId(annotation.getOriginalDetailId());
        vo.setClassName(annotation.getClassName());
        vo.setConfidence(annotation.getConfidence());
        vo.setX1(annotation.getX1());
        vo.setY1(annotation.getY1());
        vo.setX2(annotation.getX2());
        vo.setY2(annotation.getY2());
        vo.setSourceType(annotation.getSourceType());
        return vo;
    }

    private void addFileToZip(ZipOutputStream output, String rawPath, String entryName) throws IOException {
        Path path = fileStorageService.resolveManagedFile(rawPath);
        if (path == null || !Files.isRegularFile(path)) {
            return;
        }
        output.putNextEntry(new ZipEntry(entryName));
        try (BufferedInputStream input = new BufferedInputStream(Files.newInputStream(path))) {
            input.transferTo(output);
        }
        output.closeEntry();
    }

    private String buildAccessUrl(String relativePath) {
        String prefix = fileUploadProperties.getAccessUrlPrefix();
        if (!prefix.endsWith("/")) {
            prefix += "/";
        }
        return prefix + relativePath.replace('\\', '/');
    }

    private LocalDateTime parseDateTime(String value, String label) {
        if (!hasText(value)) {
            return null;
        }
        try {
            return LocalDateTime.parse(value.trim(), DATE_TIME_FORMATTER);
        } catch (DateTimeParseException e) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, label + "格式应为 yyyy-MM-dd HH:mm:ss");
        }
    }

    private void validateQualityScoreRange(Double minScore, Double maxScore) {
        if (minScore != null && (!Double.isFinite(minScore) || minScore < 0 || minScore > 100)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "minQualityScore 必须在 0 到 100 之间");
        }
        if (maxScore != null && (!Double.isFinite(maxScore) || maxScore < 0 || maxScore > 100)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "maxQualityScore 必须在 0 到 100 之间");
        }
        if (minScore != null && maxScore != null && minScore > maxScore) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "最低质量分不能高于最高质量分");
        }
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("质量评价结果序列化失败", e);
        }
    }

    private <T> T readJson(String value, TypeReference<T> type, T fallback) {
        if (!hasText(value)) return fallback;
        try {
            return objectMapper.readValue(value, type);
        } catch (JsonProcessingException e) {
            log.warn("质量评价快照解析失败", e);
            return fallback;
        }
    }

    private String failureMessage(Exception e) {
        String message = e.getMessage();
        if (message == null || message.isBlank()) {
            message = e.getClass().getSimpleName();
        }
        return "推理失败：" + truncate(message, 1900);
    }

    private String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength);
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private String newBatchSuffix() {
        return LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"))
                + "_" + UUID.randomUUID().toString().substring(0, 8);
    }

    private String nullToEmpty(String value) {
        return value == null ? "" : value;
    }

    private String numberText(Number value) {
        return value == null ? "" : value.toString();
    }

    private String ratioPercentText(Double ratio) {
        return ratio == null ? "" : String.format(Locale.ROOT, "%.2f%%", ratio * 100);
    }

    private String imageSize(DetectRecord record) {
        if (record.getImageWidth() == null || record.getImageHeight() == null) {
            return "";
        }
        return record.getImageWidth() + "x" + record.getImageHeight();
    }

    private String safeCsv(String value) {
        if (value == null) {
            return "";
        }
        String protectedValue = value;
        if (!value.isEmpty() && "=+-@".indexOf(value.charAt(0)) >= 0) {
            protectedValue = "'" + value;
        }
        return "\"" + protectedValue.replace("\"", "\"\"") + "\"";
    }

    private String safeFileName(String value) {
        if (value == null || value.isBlank()) {
            return "unknown.jpg";
        }
        return value.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_");
    }
}
