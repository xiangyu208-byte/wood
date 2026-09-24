package com.example.wooddetect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.common.DetectionStatus;
import com.example.wooddetect.common.InferenceServiceException;
import com.example.wooddetect.config.FileUploadProperties;
import com.example.wooddetect.dto.PythonDetectResponseDTO;
import com.example.wooddetect.entity.DetectBatch;
import com.example.wooddetect.entity.DetectDetail;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.mapper.DetectBatchMapper;
import com.example.wooddetect.mapper.DetectDetailMapper;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.example.wooddetect.service.DetectService;
import com.example.wooddetect.service.FileStorageService;
import com.example.wooddetect.util.PythonDetectClient;
import com.example.wooddetect.vo.BatchTaskVO;
import com.example.wooddetect.vo.DetectDetailVO;
import com.example.wooddetect.vo.DetectHistoryVO;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.PageResultVO;
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
import java.util.Set;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
public class DetectServiceImpl implements DetectService {

    private static final Logger log = LoggerFactory.getLogger(DetectServiceImpl.class);
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final Set<String> RECORD_STATUSES = Set.of(
            DetectionStatus.PENDING, DetectionStatus.PROCESSING, DetectionStatus.SUCCESS, DetectionStatus.FAIL);
    private static final Set<String> SOURCE_TYPES = Set.of("UPLOAD", "CAMERA");

    private final DetectRecordMapper detectRecordMapper;
    private final DetectDetailMapper detectDetailMapper;
    private final DetectBatchMapper detectBatchMapper;
    private final FileUploadProperties fileUploadProperties;
    private final FileStorageService fileStorageService;
    private final PythonDetectClient pythonDetectClient;
    private final TransactionTemplate transactionTemplate;
    private final TaskExecutor detectionTaskExecutor;

    public DetectServiceImpl(
            DetectRecordMapper detectRecordMapper,
            DetectDetailMapper detectDetailMapper,
            DetectBatchMapper detectBatchMapper,
            FileUploadProperties fileUploadProperties,
            FileStorageService fileStorageService,
            PythonDetectClient pythonDetectClient,
            PlatformTransactionManager transactionManager,
            @Qualifier("detectionTaskExecutor") TaskExecutor detectionTaskExecutor
    ) {
        this.detectRecordMapper = detectRecordMapper;
        this.detectDetailMapper = detectDetailMapper;
        this.detectBatchMapper = detectBatchMapper;
        this.fileUploadProperties = fileUploadProperties;
        this.fileStorageService = fileStorageService;
        this.pythonDetectClient = pythonDetectClient;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
        this.detectionTaskExecutor = detectionTaskExecutor;
    }

    @Override
    public DetectResponseVO uploadAndDetect(MultipartFile file) {
        fileStorageService.validateImage(file);
        return processNewFile(file, null, "UPLOAD", true);
    }

    @Override
    public DetectResponseVO cameraUploadAndDetect(MultipartFile file) {
        fileStorageService.validateImage(file);
        return processNewFile(file, "CAMERA_" + newBatchSuffix(), "CAMERA", true);
    }

    @Override
    public List<DetectResponseVO> batchUploadAndDetect(MultipartFile[] files) {
        validateBatch(files);
        String batchNo = "BATCH_" + newBatchSuffix();
        DetectBatch batch = createBatch(batchNo, files.length, DetectionStatus.BATCH_PROCESSING);
        List<DetectResponseVO> results = new ArrayList<>();

        for (MultipartFile file : files) {
            DetectResponseVO result = processNewFile(file, batchNo, "UPLOAD", false);
            results.add(result);
            updateBatchProgress(batch.getId(), DetectionStatus.SUCCESS.equals(result.getStatus()));
        }
        finalizeBatch(batch.getId());
        return results;
    }

    @Override
    public BatchTaskVO createAsyncBatch(MultipartFile[] files) {
        validateBatch(files);
        String batchNo = "ASYNC_" + newBatchSuffix();
        DetectBatch batch = createBatch(batchNo, files.length, DetectionStatus.BATCH_PENDING);
        List<Long> recordIds = new ArrayList<>();
        List<String> storedPaths = new ArrayList<>();

        try {
            for (MultipartFile file : files) {
                FileStorageService.StoredImage stored = fileStorageService.storeImage(file, "original");
                storedPaths.add(stored.absolutePath());
                DetectRecord record = createRecord(stored, batchNo, "UPLOAD", DetectionStatus.PENDING);
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
        vo.setStatus(batch.getStatus());
        vo.setCreateTime(batch.getCreateTime());
        vo.setUpdateTime(batch.getUpdateTime());
        vo.setItems(records.stream().map(record -> toResponseVO(record, List.of())).toList());
        return vo;
    }

    private void processQueuedBatch(Long batchId, List<Long> recordIds) {
        setBatchStatus(batchId, DetectionStatus.BATCH_PROCESSING);
        for (Long recordId : recordIds) {
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
        finalizeBatch(batchId);
    }

    private DetectResponseVO processNewFile(
            MultipartFile file, String batchNo, String sourceType, boolean throwOnInferenceFailure) {
        FileStorageService.StoredImage stored = fileStorageService.storeImage(file, "original");
        DetectRecord record;
        try {
            record = createRecord(stored, batchNo, sourceType, DetectionStatus.PROCESSING);
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
            response = pythonDetectClient.detect(record.getImagePath());
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
            FileStorageService.StoredImage stored, String batchNo, String sourceType, String status) {
        DetectRecord record = new DetectRecord();
        LocalDateTime now = LocalDateTime.now();
        record.setImageName(stored.originalName());
        record.setImagePath(stored.absolutePath());
        record.setImageUrl(buildAccessUrl(stored.relativePath()));
        record.setTotalCount(0);
        record.setStatus(status);
        record.setBatchNo(batchNo);
        record.setSourceType(sourceType);
        record.setCreateTime(now);
        record.setUpdateTime(now);
        transactionTemplate.executeWithoutResult(transactionStatus -> detectRecordMapper.insert(record));
        if (record.getId() == null) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "创建检测记录失败");
        }
        return record;
    }

    private void persistSuccess(Long recordId, PythonDetectResponseDTO response) {
        transactionTemplate.executeWithoutResult(status -> {
            DetectRecord record = requireRecord(recordId);
            if (!DetectionStatus.PROCESSING.equals(record.getStatus())) {
                throw new IllegalStateException("非法状态转换：" + record.getStatus() + " -> SUCCESS");
            }
            record.setResultImagePath(response.getResultImagePath());
            record.setResultImageUrl(response.getResultImageUrl());
            record.setTotalCount(response.getTotalCount() == null ? 0 : response.getTotalCount());
            record.setStatus(DetectionStatus.SUCCESS);
            record.setErrorMessage(null);
            record.setUpdateTime(LocalDateTime.now());
            detectRecordMapper.updateById(record);
            saveDetectDetails(recordId, response.getDetails());
        });
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
            String sourceType, String hasDefect, String startTime, String endTime) {
        int safePage = page == null ? 1 : page;
        int safeSize = size == null ? 10 : size;
        if (safePage < 1 || safeSize < 1 || safeSize > 100) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "页码必须大于 0，每页数量必须在 1 到 100 之间");
        }

        QueryWrapper<DetectRecord> wrapper = buildHistoryQueryWrapper(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime);
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
        return toResponseVO(record, details);
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
            String hasDefect, String startTime, String endTime) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime);
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
            String hasDefect, String startTime, String endTime, HttpServletResponse response) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime);
        response.setContentType("text/csv;charset=UTF-8");
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setHeader("Content-Disposition", "attachment; filename=detect_history.csv");
        try (PrintWriter writer = response.getWriter()) {
            writer.write('\uFEFF');
            writer.println("记录ID,批次号,来源类型,图片名称,原图URL,结果图URL,缺陷数,状态,失败原因,创建时间");
            for (DetectRecord record : records) {
                writer.printf("%d,%s,%s,%s,%s,%s,%d,%s,%s,%s%n",
                        record.getId(), safeCsv(record.getBatchNo()), safeCsv(record.getSourceType()),
                        safeCsv(record.getImageName()), safeCsv(record.getImageUrl()),
                        safeCsv(record.getResultImageUrl()), record.getTotalCount() == null ? 0 : record.getTotalCount(),
                        safeCsv(record.getStatus()), safeCsv(record.getErrorMessage()),
                        record.getCreateTime() == null ? "" : record.getCreateTime());
            }
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "导出 CSV 失败", e);
        }
    }

    @Override
    public void exportHistoryExcel(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String startTime, String endTime, HttpServletResponse response) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime);
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setHeader("Content-Disposition", "attachment; filename=detect_history.xlsx");
        try (XSSFWorkbook workbook = new XSSFWorkbook()) {
            Sheet sheet = workbook.createSheet("历史记录");
            String[] headers = {"记录ID", "批次号", "来源类型", "图片名称", "原图URL", "结果图URL", "缺陷数", "状态", "失败原因", "创建时间"};
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
                row.createCell(9).setCellValue(record.getCreateTime() == null ? "" : record.getCreateTime().toString());
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
            String hasDefect, String startTime, String endTime, HttpServletResponse response) {
        List<DetectRecord> records = listHistoryRecords(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime);
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
            String hasDefect, String startTime, String endTime) {
        return detectRecordMapper.selectList(buildHistoryQueryWrapper(
                imageName, status, batchNo, sourceType, hasDefect, startTime, endTime));
    }

    private QueryWrapper<DetectRecord> buildHistoryQueryWrapper(
            String imageName, String status, String batchNo, String sourceType,
            String hasDefect, String startTime, String endTime) {
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
                batch.setProcessedCount(batch.getTotalCount());
                batch.setFailCount(batch.getTotalCount());
                batch.setStatus(DetectionStatus.BATCH_FAIL);
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
        vo.setCreateTime(record.getCreateTime());
        vo.setDetails(details.stream().map(this::toDetailVO).toList());
        return vo;
    }

    private DetectDetailVO toDetailVO(DetectDetail detail) {
        DetectDetailVO vo = new DetectDetailVO();
        vo.setClassName(detail.getClassName());
        vo.setConfidence(detail.getConfidence());
        vo.setX1(detail.getX1());
        vo.setY1(detail.getY1());
        vo.setX2(detail.getX2());
        vo.setY2(detail.getY2());
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
