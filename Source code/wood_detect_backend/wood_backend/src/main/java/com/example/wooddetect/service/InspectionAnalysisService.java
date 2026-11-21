package com.example.wooddetect.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.wooddetect.common.BusinessException;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.entity.DetectReviewAnnotation;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.example.wooddetect.mapper.DetectReviewAnnotationMapper;
import com.example.wooddetect.vo.QualityDeductionVO;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class InspectionAnalysisService {
    public record Scope(String materialBatch, List<Long> recordIds) {}
    public record Photo(long id, String name, String reviewStatus, Double score, Double deduction,
                        Map<String,Integer> defects, Map<String,Double> deductions) {}
    public record Facts(String materialBatch, int total, List<Photo> photos, Map<String,Integer> defects) {}
    public record ResultView(Facts facts, String report) {}

    private final DetectRecordMapper records;
    private final DetectReviewAnnotationMapper annotations;
    private final QualityScoringService scoring;
    private final MaterialBatchService batches;
    private final DeepSeekService model;
    private final JdbcTemplate db;
    private final ObjectMapper json;

    public InspectionAnalysisService(DetectRecordMapper records, DetectReviewAnnotationMapper annotations,
                                    QualityScoringService scoring, MaterialBatchService batches,
                                    DeepSeekService model, JdbcTemplate db, ObjectMapper json) {
        this.records = records;
        this.annotations = annotations;
        this.scoring = scoring;
        this.batches = batches;
        this.model = model;
        this.db = db;
        this.json = json;
    }

    @Transactional(readOnly = true)
    public Facts facts(Scope scope) {
        String code = batches.resolve(scope.materialBatch());
        List<Long> ids = scope.recordIds() == null ? List.of() : scope.recordIds();
        if ((code == null) == ids.isEmpty() || ids.size() > 1000 || ids.stream().anyMatch(id -> id == null || id <= 0)) {
            throw new BusinessException(HttpStatus.BAD_REQUEST, "请选择一个板材批次或 1–1000 条历史记录");
        }
        var query = new QueryWrapper<DetectRecord>().orderByAsc("id");
        if (code != null) query.eq("material_batch", code);
        else query.in("id", ids);
        var rows = records.selectList(query);
        if (code == null && rows.size() != new HashSet<>(ids).size())
            throw new BusinessException(HttpStatus.NOT_FOUND, "部分记录已删除，请刷新后重新选择");

        var reviewed = rows.stream().filter(r -> "SUCCESS".equals(r.getStatus()) && reviewed(r))
                .map(DetectRecord::getId).toList();
        var boxes = new HashMap<Long,List<QualityScoringService.QualityBox>>();
        for (int i = 0; i < reviewed.size(); i += 500) {
            var chunk = reviewed.subList(i, Math.min(i + 500, reviewed.size()));
            var list = annotations.selectList(new QueryWrapper<DetectReviewAnnotation>().in("record_id", chunk));
            for (var a : list) boxes.computeIfAbsent(a.getRecordId(), k -> new ArrayList<>()).add(
                    new QualityScoringService.QualityBox(a.getClassName(), a.getX1(), a.getY1(), a.getX2(), a.getY2()));
        }

        var photos = new ArrayList<Photo>();
        var totals = new TreeMap<String,Integer>();
        for (var row : rows) {
            if (!"SUCCESS".equals(row.getStatus())) continue;
            Double score = row.getQualityScore();
            Map<String,Integer> counts = decode(row.getDefectCountsJson(), new TypeReference<TreeMap<String,Integer>>() {}, new TreeMap<>());
            List<QualityDeductionVO> deductions = decode(row.getQualityDeductionsJson(), new TypeReference<List<QualityDeductionVO>>() {}, List.of());
            if (reviewed(row) && row.getImageWidth() != null && row.getImageHeight() != null
                    && row.getImageWidth() > 0 && row.getImageHeight() > 0) {
                var assessment = scoring.assess(boxes.getOrDefault(row.getId(), List.of()), row.getImageWidth(), row.getImageHeight());
                score = assessment.score();
                counts = new TreeMap<>(assessment.defectCounts());
                deductions = assessment.deductions();
            }
            counts.forEach((k, v) -> totals.merge(k, v, Integer::sum));
            var breakdown = new TreeMap<String,Double>();
            for (var d : deductions) breakdown.merge(d.getLabel(), d.getPoints(), Double::sum);
            double points = deductions.stream().mapToDouble(QualityDeductionVO::getPoints).sum();
            photos.add(new Photo(row.getId(), row.getImageName(), row.getReviewStatus(), score,
                    score == null ? null : Math.round(points * 100.0) / 100.0, counts, breakdown));
        }
        return new Facts(code, rows.size(), photos, totals);
    }

    private boolean reviewed(DetectRecord row) {
        return row.getReviewStatus() != null && !"UNREVIEWED".equals(row.getReviewStatus());
    }

    private <T> T decode(String value, TypeReference<T> type, T empty) {
        if (value == null || value.isBlank()) return empty;
        try { return json.readValue(value, type); }
        catch (java.io.IOException e) { throw new IllegalStateException("历史评分数据无法读取", e); }
    }

    public ResultView result(Facts facts, boolean generate) {
        String fingerprint;
        try {
            fingerprint = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(json.writeValueAsBytes(facts)));
        } catch (java.io.IOException | NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
        var previous = db.queryForList("SELECT report_text FROM inspection_analysis WHERE fingerprint=?", String.class, fingerprint);
        if (!previous.isEmpty()) return new ResultView(facts, previous.get(0));
        if (!generate) return new ResultView(facts, null);
        if (facts.photos().isEmpty()) throw new BusinessException(HttpStatus.BAD_REQUEST, "当前范围内还没有识别成功的图片");
        String report = model.report(modelFacts(facts));
        db.update("INSERT INTO inspection_analysis(fingerprint,report_text) VALUES (?,?) ON DUPLICATE KEY UPDATE fingerprint=VALUES(fingerprint)",
                fingerprint, report);
        return new ResultView(facts, db.queryForObject("SELECT report_text FROM inspection_analysis WHERE fingerprint=?", String.class, fingerprint));
    }

    private static Map<String,Integer> chineseCounts(Map<String,Integer> counts) {
        var labels = new TreeMap<String,Integer>();
        counts.forEach((k,v) -> labels.merge(QualityScoringService.classLabel(k), v, Integer::sum));
        return labels;
    }

    private static String reviewLabel(String status) {
        return switch (status == null ? "" : status) {
            case "CORRECTED" -> "已人工修正";
            case "CORRECT" -> "人工确认正确";
            case "INCORRECT" -> "人工标记错误";
            default -> "未复核";
        };
    }

    private Map<String,Object> modelFacts(Facts facts) {
        var data = new LinkedHashMap<String,Object>();
        data.put("范围", facts.materialBatch() == null ? "所选图片" : facts.materialBatch());
        data.put("总记录数", facts.total());
        data.put("识别成功图片数", facts.photos().size());
        data.put("逐图累计缺陷框数", chineseCounts(facts.defects()));
        var breakdown = new TreeMap<String,Double>();
        facts.photos().forEach(p -> p.deductions().forEach((label,points) -> breakdown.merge(label, points, Double::sum)));
        breakdown.replaceAll((label,points) -> Math.round(points * 100.0) / 100.0);
        data.put("全批各项规则扣分", breakdown);
        var scored = facts.photos().stream().filter(p -> p.score() != null).toList();
        var stats = scored.stream().mapToDouble(Photo::score).summaryStatistics();
        if (stats.getCount() > 0) {
            data.put("评分统计", Map.of("已评分图片", stats.getCount(), "均分", Math.round(stats.getAverage()*100)/100.0,
                    "最低分", stats.getMin(), "最高分", stats.getMax()));
        }
        data.put("规则扣分合计（评分封底前）", scored.stream().mapToDouble(Photo::deduction).sum());
        var examples = facts.photos().size() <= 100 ? facts.photos() : scored.stream()
                .sorted(Comparator.comparing(Photo::score).thenComparing(Photo::id)).limit(100).toList();
        data.put(examples.size() == facts.photos().size() ? "逐图结果" : "最低分图片样例", examples.stream()
                .map(p -> Arrays.asList(p.id(), p.score(), p.deduction(), chineseCounts(p.defects()), reviewLabel(p.reviewStatus()), p.deductions())).toList());
        data.put("逐图字段", List.of("记录号", "质量分", "规则扣分", "缺陷类型及数量", "人工复核状态", "各项扣分"));
        return data;
    }
}
