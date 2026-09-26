package com.example.wooddetect.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.common.DetectionStatus;
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
import com.example.wooddetect.service.ReviewService;
import com.example.wooddetect.vo.DetectResponseVO;
import com.example.wooddetect.vo.ModelVersionStatsVO;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@Service
public class ReviewServiceImpl implements ReviewService {

    private static final List<String> CLASS_NAMES = List.of(
            "dry_knot", "sound_knot", "edge_knot", "small_knot", "split", "wave");
    private static final Map<String, Integer> CLASS_IDS = classIds();
    private static final Set<String> REVIEW_STATUSES = Set.of("CORRECT", "INCORRECT", "CORRECTED");

    private final DetectRecordMapper recordMapper;
    private final DetectDetailMapper detailMapper;
    private final DetectReviewAnnotationMapper annotationMapper;
    private final DetectService detectService;
    private final FileStorageService fileStorageService;
    private final ObjectMapper objectMapper;
    private final TransactionTemplate transactionTemplate;

    public ReviewServiceImpl(
            DetectRecordMapper recordMapper,
            DetectDetailMapper detailMapper,
            DetectReviewAnnotationMapper annotationMapper,
            DetectService detectService,
            FileStorageService fileStorageService,
            ObjectMapper objectMapper,
            PlatformTransactionManager transactionManager) {
        this.recordMapper = recordMapper;
        this.detailMapper = detailMapper;
        this.annotationMapper = annotationMapper;
        this.detectService = detectService;
        this.fileStorageService = fileStorageService;
        this.objectMapper = objectMapper;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    @Override
    public DetectResponseVO submitReview(Long recordId, ReviewSubmissionDTO submission) {
        DetectRecord record = requireReviewableRecord(recordId);
        String reviewStatus = normalizeReviewStatus(submission.getReviewStatus());
        List<DetectDetail> originalDetails = detailMapper.selectList(
                new QueryWrapper<DetectDetail>().eq("record_id", recordId).orderByAsc("id"));
        Map<Long, DetectDetail> originalsById = new HashMap<>();
        originalDetails.forEach(detail -> originalsById.put(detail.getId(), detail));

        List<ReviewAnnotationDTO> requested = submission.getAnnotations() == null
                ? List.of() : submission.getAnnotations();
        if ("CORRECT".equals(reviewStatus) && requested.isEmpty()) {
            requested = originalDetails.stream()
                    .filter(detail -> !"suspected_anomaly".equals(detail.getClassName()))
                    .map(this::fromOriginalDetail)
                    .toList();
        }
        if ("INCORRECT".equals(reviewStatus) && !requested.isEmpty()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST,
                    "标记为错误时不能同时提交标注框；如需修正或补框，请使用 CORRECTED");
        }

        List<DetectReviewAnnotation> annotations = new ArrayList<>();
        Set<Long> referencedOriginals = new java.util.HashSet<>();
        for (ReviewAnnotationDTO item : requested) {
            if (item.getOriginalDetailId() != null && !referencedOriginals.add(item.getOriginalDetailId())) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "同一个原始检测框不能重复提交");
            }
            annotations.add(validateAndConvert(item, record, originalsById));
        }

        List<DetectReviewAnnotation> finalAnnotations = annotations;
        String comment = normalizeComment(submission.getComment());
        transactionTemplate.executeWithoutResult(status -> {
            annotationMapper.delete(new QueryWrapper<DetectReviewAnnotation>().eq("record_id", recordId));
            LocalDateTime now = LocalDateTime.now();
            finalAnnotations.forEach(annotation -> {
                annotation.setRecordId(recordId);
                annotation.setCreateTime(now);
                annotationMapper.insert(annotation);
            });
            DetectRecord latest = recordMapper.selectById(recordId);
            latest.setReviewStatus(reviewStatus);
            latest.setReviewComment(comment);
            latest.setReviewedAt(now);
            latest.setUpdateTime(now);
            recordMapper.updateById(latest);
        });
        return detectService.getDetail(recordId);
    }

    @Override
    public void exportYoloDataset(
            List<Long> recordIds,
            String reviewStatus,
            String modelVersion,
            HttpServletResponse response) {
        QueryWrapper<DetectRecord> query = new QueryWrapper<DetectRecord>()
                .eq("status", DetectionStatus.SUCCESS)
                .ne("review_status", "UNREVIEWED")
                .orderByAsc("id");
        if (recordIds != null && !recordIds.isEmpty()) {
            List<Long> normalizedIds = recordIds.stream().filter(Objects::nonNull).distinct().toList();
            if (normalizedIds.isEmpty() || normalizedIds.size() > 1000) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "导出记录数量必须在 1 到 1000 之间");
            }
            query.in("id", normalizedIds);
        }
        if (hasText(reviewStatus)) query.eq("review_status", normalizeReviewStatus(reviewStatus));
        if (hasText(modelVersion)) query.eq("model_version", modelVersion.trim());

        List<DetectRecord> records = recordMapper.selectList(query);
        if (records.isEmpty()) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "没有已复核记录可导出");
        }
        List<ExportItem> exportItems = records.stream()
                .map(record -> new ExportItem(record, fileStorageService.resolveManagedFile(record.getImagePath())))
                .filter(item -> item.imagePath() != null && Files.isRegularFile(item.imagePath()))
                .toList();
        if (exportItems.isEmpty()) {
            throw new BusinessException(HttpStatus.NOT_FOUND, "已复核记录的原图均不存在，无法导出");
        }

        response.setContentType("application/zip");
        response.setHeader("Content-Disposition", "attachment; filename=wood_active_learning_yolo.zip");
        try (ZipOutputStream output = new ZipOutputStream(response.getOutputStream(), StandardCharsets.UTF_8)) {
            List<Map<String, Object>> manifestRecords = new ArrayList<>();
            int exportedCount = 0;
            for (ExportItem exportItem : exportItems) {
                DetectRecord record = exportItem.record();
                String imageName = record.getId() + "_" + safeFileName(record.getImageName());
                String labelName = stripExtension(imageName) + ".txt";
                addFile(output, exportItem.imagePath(), "wood-active-learning/images/train/" + imageName);
                List<DetectReviewAnnotation> annotations = annotationMapper.selectList(
                        new QueryWrapper<DetectReviewAnnotation>()
                                .eq("record_id", record.getId()).orderByAsc("id"));
                addText(output, "wood-active-learning/labels/train/" + labelName,
                        yoloLabels(record, annotations));

                Map<String, Object> item = new LinkedHashMap<>();
                item.put("recordId", record.getId());
                item.put("image", imageName);
                item.put("label", labelName);
                item.put("modelVersion", record.getModelVersion());
                item.put("reviewStatus", record.getReviewStatus());
                item.put("reviewedAt", record.getReviewedAt() == null ? null : record.getReviewedAt().toString());
                item.put("annotationCount", annotations.size());
                manifestRecords.add(item);
                exportedCount++;
            }
            addText(output, "wood-active-learning/data.yaml", dataYaml());
            addText(output, "wood-active-learning/README.txt", exportReadme());
            Map<String, Object> manifest = new LinkedHashMap<>();
            manifest.put("createdAt", LocalDateTime.now().toString());
            manifest.put("format", "YOLO detection");
            manifest.put("classNames", CLASS_NAMES);
            manifest.put("recordCount", exportedCount);
            manifest.put("records", manifestRecords);
            addText(output, "wood-active-learning/manifest.json",
                    objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(manifest));
            output.finish();
        } catch (IOException e) {
            throw new BusinessException(HttpStatus.INTERNAL_SERVER_ERROR, "导出 YOLO 数据包失败", e);
        }
    }

    @Override
    public List<ModelVersionStatsVO> getModelVersionStats() {
        List<ModelVersionStatsVO> versions = recordMapper.selectModelVersionStats();
        for (int i = 0; i < versions.size(); i++) {
            ModelVersionStatsVO current = versions.get(i);
            long reviewed = value(current.getReviewedCount());
            current.setConfirmationRate(reviewed == 0 ? null : round4(value(current.getCorrectCount()) / (double) reviewed));
            current.setCorrectionRate(reviewed == 0 ? null : round4(value(current.getCorrectedCount()) / (double) reviewed));
            if (i + 1 < versions.size()) {
                ModelVersionStatsVO previous = versions.get(i + 1);
                long previousReviewed = value(previous.getReviewedCount());
                Double previousRate = previousReviewed == 0 ? null
                        : round4(value(previous.getCorrectCount()) / (double) previousReviewed);
                Double previousCorrectionRate = previousReviewed == 0 ? null
                        : round4(value(previous.getCorrectedCount()) / (double) previousReviewed);
                if (current.getConfirmationRate() != null && previousRate != null) {
                    current.setConfirmationRateChange(round4(current.getConfirmationRate() - previousRate));
                }
                if (current.getCorrectionRate() != null && previousCorrectionRate != null) {
                    current.setCorrectionRateChange(round4(current.getCorrectionRate() - previousCorrectionRate));
                }
                if (current.getAverageQualityScore() != null && previous.getAverageQualityScore() != null) {
                    current.setAverageQualityScoreChange(round2(
                            current.getAverageQualityScore() - previous.getAverageQualityScore()));
                }
            }
            if (current.getAverageQualityScore() != null) {
                current.setAverageQualityScore(round2(current.getAverageQualityScore()));
            }
            if (current.getAverageInferenceDurationMs() != null) {
                current.setAverageInferenceDurationMs(round2(current.getAverageInferenceDurationMs()));
            }
        }
        return versions;
    }

    private DetectRecord requireReviewableRecord(Long recordId) {
        if (recordId == null || recordId <= 0) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "记录 ID 不合法");
        }
        DetectRecord record = recordMapper.selectById(recordId);
        if (record == null) throw new BusinessException(HttpStatus.NOT_FOUND, "检测记录不存在");
        if (!DetectionStatus.SUCCESS.equals(record.getStatus())) {
            throw new BusinessException(HttpStatus.CONFLICT, "只有识别成功的记录可以人工复核");
        }
        if (record.getImageWidth() == null || record.getImageHeight() == null
                || record.getImageWidth() <= 0 || record.getImageHeight() <= 0) {
            throw new BusinessException(HttpStatus.CONFLICT, "记录缺少图片尺寸，无法校验标注框");
        }
        return record;
    }

    private DetectReviewAnnotation validateAndConvert(
            ReviewAnnotationDTO item,
            DetectRecord record,
            Map<Long, DetectDetail> originalsById) {
        String className = item.getClassName() == null ? "" : item.getClassName().trim().toLowerCase(Locale.ROOT);
        if (!CLASS_IDS.containsKey(className)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "不支持的复核类别：" + item.getClassName());
        }
        if (item.getX1() == null || item.getY1() == null || item.getX2() == null || item.getY2() == null
                || item.getX1() < 0 || item.getY1() < 0
                || item.getX2() <= item.getX1() || item.getY2() <= item.getY1()
                || item.getX2() > record.getImageWidth() || item.getY2() > record.getImageHeight()) {
            throw new BusinessException(HttpStatus.BAD_REQUEST,
                    "复核框必须位于图片范围内，且右下坐标大于左上坐标");
        }

        DetectDetail original = null;
        if (item.getOriginalDetailId() != null) {
            original = originalsById.get(item.getOriginalDetailId());
            if (original == null) {
                throw new BusinessException(HttpStatus.BAD_REQUEST, "原始检测框不属于当前记录");
            }
        }
        boolean unchanged = original != null
                && Objects.equals(original.getClassName(), className)
                && Objects.equals(original.getX1(), item.getX1())
                && Objects.equals(original.getY1(), item.getY1())
                && Objects.equals(original.getX2(), item.getX2())
                && Objects.equals(original.getY2(), item.getY2());

        DetectReviewAnnotation annotation = new DetectReviewAnnotation();
        annotation.setOriginalDetailId(item.getOriginalDetailId());
        annotation.setClassName(className);
        annotation.setConfidence(original == null ? null : original.getConfidence());
        annotation.setX1(item.getX1());
        annotation.setY1(item.getY1());
        annotation.setX2(item.getX2());
        annotation.setY2(item.getY2());
        annotation.setSourceType(original == null ? "HUMAN_ADDED" : unchanged ? "MODEL_CONFIRMED" : "HUMAN_CORRECTED");
        return annotation;
    }

    private ReviewAnnotationDTO fromOriginalDetail(DetectDetail detail) {
        ReviewAnnotationDTO item = new ReviewAnnotationDTO();
        item.setOriginalDetailId(detail.getId());
        item.setClassName(detail.getClassName());
        item.setX1(detail.getX1());
        item.setY1(detail.getY1());
        item.setX2(detail.getX2());
        item.setY2(detail.getY2());
        return item;
    }

    private String yoloLabels(DetectRecord record, List<DetectReviewAnnotation> annotations) {
        StringBuilder labels = new StringBuilder();
        for (DetectReviewAnnotation item : annotations) {
            Integer classId = CLASS_IDS.get(item.getClassName());
            if (classId == null) continue;
            double centerX = (item.getX1() + item.getX2()) / 2.0 / record.getImageWidth();
            double centerY = (item.getY1() + item.getY2()) / 2.0 / record.getImageHeight();
            double width = (item.getX2() - item.getX1()) / (double) record.getImageWidth();
            double height = (item.getY2() - item.getY1()) / (double) record.getImageHeight();
            labels.append(String.format(Locale.ROOT, "%d %.6f %.6f %.6f %.6f",
                    classId, centerX, centerY, width, height)).append('\n');
        }
        return labels.toString();
    }

    private String dataYaml() {
        StringBuilder yaml = new StringBuilder("path: .\ntrain: images/train\nval: images/train\nnc: 6\nnames:\n");
        for (int i = 0; i < CLASS_NAMES.size(); i++) {
            yaml.append("  ").append(i).append(": ").append(CLASS_NAMES.get(i)).append('\n');
        }
        return yaml.toString();
    }

    private String exportReadme() {
        return "本数据包仅包含已人工复核的记录。\n"
                + "images/train 为原图，labels/train 为 YOLO 检测标签，空标签表示人工确认无目标。\n"
                + "请在训练前划分独立验证集并检查 manifest.json，不要直接使用 train 目录评估模型。\n";
    }

    private void addFile(ZipOutputStream output, Path path, String entryName) throws IOException {
        output.putNextEntry(new ZipEntry(entryName));
        try (BufferedInputStream input = new BufferedInputStream(Files.newInputStream(path))) {
            input.transferTo(output);
        }
        output.closeEntry();
    }

    private void addText(ZipOutputStream output, String entryName, String content) throws IOException {
        output.putNextEntry(new ZipEntry(entryName));
        output.write(content.getBytes(StandardCharsets.UTF_8));
        output.closeEntry();
    }

    private String normalizeReviewStatus(String status) {
        String normalized = status == null ? "" : status.trim().toUpperCase(Locale.ROOT);
        if (!REVIEW_STATUSES.contains(normalized)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST,
                    "reviewStatus 仅支持 CORRECT、INCORRECT 或 CORRECTED");
        }
        return normalized;
    }

    private String normalizeComment(String comment) {
        if (!hasText(comment)) return null;
        return comment.trim();
    }

    private String safeFileName(String value) {
        if (!hasText(value)) return "unknown.jpg";
        return value.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_");
    }

    private String stripExtension(String fileName) {
        int dot = fileName.lastIndexOf('.');
        return dot > 0 ? fileName.substring(0, dot) : fileName;
    }

    private boolean hasText(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private long value(Long value) {
        return value == null ? 0 : value;
    }

    private double round2(double value) {
        return Math.round(value * 100.0) / 100.0;
    }

    private double round4(double value) {
        return Math.round(value * 10_000.0) / 10_000.0;
    }

    private static Map<String, Integer> classIds() {
        Map<String, Integer> result = new LinkedHashMap<>();
        for (int i = 0; i < CLASS_NAMES.size(); i++) result.put(CLASS_NAMES.get(i), i);
        return result;
    }

    private record ExportItem(DetectRecord record, Path imagePath) {}
}
