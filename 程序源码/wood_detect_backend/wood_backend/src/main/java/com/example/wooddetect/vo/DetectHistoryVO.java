package com.example.wooddetect.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class DetectHistoryVO {

    /**
     * 识别记录ID
     */
    private Long recordId;

    /**
     * 批次号
     */
    private String batchNo;

    /**
     * 来源类型：UPLOAD / CAMERA
     */
    private String sourceType;
    private String modelMode;
    private Double confidenceThreshold;
    private String inferencePrecision;

    /**
     * 原始文件名
     */
    private String imageName;

    /**
     * 原图访问URL
     */
    private String imageUrl;

    /**
     * 结果图访问URL
     */
    private String resultImageUrl;

    /**
     * 检测总数
     */
    private Integer totalCount;

    /**
     * 当前状态
     */
    private String status;

    /**
     * 失败原因
     */
    private String errorMessage;

    /**
     * 创建时间
     */
    private LocalDateTime createTime;
}
