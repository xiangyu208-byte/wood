package com.example.wooddetect.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.wooddetect.common.DetectionStatus;
import com.example.wooddetect.entity.DetectDetail;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.mapper.DetectDetailMapper;
import com.example.wooddetect.mapper.DetectRecordMapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.util.List;

/** 为升级前已有且具备图片尺寸的成功记录补齐质量评价快照。 */
@Component
public class QualityAssessmentBackfill {

    private static final Logger log = LoggerFactory.getLogger(QualityAssessmentBackfill.class);
    private static final int PAGE_SIZE = 200;

    private final DetectRecordMapper recordMapper;
    private final DetectDetailMapper detailMapper;
    private final QualityScoringService scoringService;
    private final ObjectMapper objectMapper;

    public QualityAssessmentBackfill(
            DetectRecordMapper recordMapper,
            DetectDetailMapper detailMapper,
            QualityScoringService scoringService,
            ObjectMapper objectMapper) {
        this.recordMapper = recordMapper;
        this.detailMapper = detailMapper;
        this.scoringService = scoringService;
        this.objectMapper = objectMapper;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void backfillMissingAssessments() {
        long cursor = 0;
        int updated = 0;
        while (true) {
            List<DetectRecord> records = recordMapper.selectList(new QueryWrapper<DetectRecord>()
                    .gt("id", cursor)
                    .eq("status", DetectionStatus.SUCCESS)
                    .isNull("quality_score")
                    .isNotNull("image_width")
                    .isNotNull("image_height")
                    .orderByAsc("id")
                    .last("LIMIT " + PAGE_SIZE));
            if (records.isEmpty()) break;
            for (DetectRecord record : records) {
                cursor = record.getId();
                try {
                    List<DetectDetail> details = detailMapper.selectList(
                            new QueryWrapper<DetectDetail>().eq("record_id", record.getId()).orderByAsc("id"));
                    QualityScoringService.Assessment assessment = scoringService.assess(
                            details.stream().map(detail -> new QualityScoringService.QualityBox(
                                    detail.getClassName(), detail.getX1(), detail.getY1(), detail.getX2(), detail.getY2()
                            )).toList(), record.getImageWidth(), record.getImageHeight());
                    record.setQualityScore(assessment.score());
                    record.setQualityGrade(assessment.grade());
                    record.setDefectAreaRatio(assessment.defectAreaRatio());
                    record.setMaxDefectAreaRatio(assessment.maxDefectAreaRatio());
                    record.setDefectCountsJson(objectMapper.writeValueAsString(assessment.defectCounts()));
                    record.setQualityDeductionsJson(objectMapper.writeValueAsString(assessment.deductions()));
                    record.setQualityRuleVersion(assessment.ruleVersion());
                    record.setQualityDisclaimer(assessment.disclaimer());
                    recordMapper.updateById(record);
                    updated++;
                } catch (Exception e) {
                    log.warn("无法为历史记录补齐质量评价, recordId={}", record.getId(), e);
                }
            }
        }
        if (updated > 0) log.info("已为 {} 条历史记录补齐质量评价", updated);
    }
}
