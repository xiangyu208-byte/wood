package com.example.wooddetect.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 每一次批量识别或单个识别任务对应的实体类
 */
@Data
@TableName("detect_record")//若不一致要写 一致的话可选这个注解
public class DetectRecord {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String imageName;

    private String imagePath;

    private String imageUrl;

    private String resultImagePath;

    private String resultImageUrl;

    private Integer totalCount;

    private String status;

    private String errorMessage;

    /**
     * 批量识别批次号
     */
    private String batchNo;

    /**
     * 识别来源：UPLOAD / CAMERA
     */
    private String sourceType;

    private String modelMode;

    private String actualMode;

    private String decisionReason;

    private Double confidenceThreshold;

    private String inferencePrecision;

    private String modelVersion;

    private Double minConfidence;

    private Boolean reviewNeeded;

    private String reviewReason;

    private String reviewStatus;

    private String reviewComment;

    private LocalDateTime reviewedAt;

    private Long inferenceDurationMs;

    private Integer tileCount;

    private Integer imageWidth;

    private Integer imageHeight;

    private Double qualityScore;

    private String qualityGrade;

    private Double defectAreaRatio;

    private Double maxDefectAreaRatio;

    private String defectCountsJson;

    private String qualityDeductionsJson;

    private String qualityRuleVersion;

    private String qualityDisclaimer;

    private LocalDateTime createTime;

    private LocalDateTime updateTime;
}
