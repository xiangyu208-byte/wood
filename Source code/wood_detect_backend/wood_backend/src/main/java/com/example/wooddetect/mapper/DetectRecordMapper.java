package com.example.wooddetect.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.wooddetect.entity.DetectRecord;
import com.example.wooddetect.vo.ModelVersionStatsVO;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 继承 MyBatis-Plus 提供的通用 Mapper 不用自己写sql
 */
public interface DetectRecordMapper extends BaseMapper<DetectRecord> {

    @Select("""
            SELECT COALESCE(model_version, 'unknown') AS modelVersion,
                   COUNT(*) AS recordCount,
                   SUM(CASE WHEN review_status <> 'UNREVIEWED' THEN 1 ELSE 0 END) AS reviewedCount,
                   SUM(CASE WHEN review_status = 'CORRECT' THEN 1 ELSE 0 END) AS correctCount,
                   SUM(CASE WHEN review_status = 'CORRECTED' THEN 1 ELSE 0 END) AS correctedCount,
                   SUM(CASE WHEN review_status = 'INCORRECT' THEN 1 ELSE 0 END) AS incorrectCount,
                   SUM(CASE WHEN review_needed = 1 THEN 1 ELSE 0 END) AS reviewNeededCount,
                   AVG(quality_score) AS averageQualityScore,
                   AVG(inference_duration_ms) AS averageInferenceDurationMs,
                   MAX(create_time) AS lastUsedAt
            FROM detect_record
            WHERE status = 'SUCCESS'
            GROUP BY COALESCE(model_version, 'unknown')
            ORDER BY MAX(create_time) DESC
            """)
    List<ModelVersionStatsVO> selectModelVersionStats();
}
