package com.example.wooddetect.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.wooddetect.common.DetectionStatus;
import com.example.wooddetect.config.ActiveLearningProperties;
import com.example.wooddetect.entity.DetectDetail;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.mapper.DetectDetailMapper;
import com.example.wooddetect.mapper.DetectRecordMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

/** 为 V6 升级前的成功记录补齐复核队列元数据，模型版本明确标记为 legacy-unknown。 */
@Component
public class ActiveLearningBackfill {
    private static final Logger log = LoggerFactory.getLogger(ActiveLearningBackfill.class);
    private static final int PAGE_SIZE = 200;

    private final DetectRecordMapper recordMapper;
    private final DetectDetailMapper detailMapper;
    private final ActiveLearningProperties properties;

    public ActiveLearningBackfill(
            DetectRecordMapper recordMapper,
            DetectDetailMapper detailMapper,
            ActiveLearningProperties properties) {
        this.recordMapper = recordMapper;
        this.detailMapper = detailMapper;
        this.properties = properties;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void backfillLegacyReviewMetadata() {
        long cursor = 0;
        int updated = 0;
        while (true) {
            List<DetectRecord> records = recordMapper.selectList(new QueryWrapper<DetectRecord>()
                    .gt("id", cursor)
                    .eq("status", DetectionStatus.SUCCESS)
                    .isNull("model_version")
                    .orderByAsc("id")
                    .last("LIMIT " + PAGE_SIZE));
            if (records.isEmpty()) break;
            for (DetectRecord record : records) {
                cursor = record.getId();
                try {
                    List<DetectDetail> details = detailMapper.selectList(
                            new QueryWrapper<DetectDetail>().eq("record_id", record.getId()));
                    Double minConfidence = details.stream()
                            .filter(detail -> !"suspected_anomaly".equals(detail.getClassName()))
                            .map(DetectDetail::getConfidence)
                            .filter(java.util.Objects::nonNull)
                            .min(Double::compareTo).orElse(null);
                    boolean suspected = details.stream()
                            .anyMatch(detail -> "suspected_anomaly".equals(detail.getClassName()));
                    boolean lowConfidence = minConfidence != null
                            && minConfidence < properties.getLowConfidenceThreshold();
                    record.setModelVersion("legacy-unknown");
                    record.setMinConfidence(minConfidence);
                    record.setReviewNeeded(suspected || lowConfidence);
                    record.setReviewReason(suspected ? "SUSPECTED_ANOMALY"
                            : lowConfidence ? "LOW_CONFIDENCE" : null);
                    if (record.getReviewStatus() == null) record.setReviewStatus("UNREVIEWED");
                    record.setUpdateTime(LocalDateTime.now());
                    recordMapper.updateById(record);
                    updated++;
                } catch (Exception e) {
                    log.warn("无法为历史记录补齐主动学习元数据, recordId={}", record.getId(), e);
                }
            }
        }
        if (updated > 0) log.info("已为 {} 条历史记录补齐主动学习元数据", updated);
    }
}
