package com.example.wooddetect.vo;

import lombok.Data;

import java.time.LocalDateTime;
import java.util.List;

@Data
public class DetectResponseVO {

    /**
     * 识别记录ID
     */
    private Long recordId;

    /**
     * 批量任务编号；单张上传时为空
     */
    private String batchNo;

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
     * 状态
     */
    private String status;

    /**
     * 错误信息
     */
    private String errorMessage;

    /**
     * 来源类型：UPLOAD / CAMERA
     */
    private String sourceType;

    /** 推理模式：FAST / STANDARD / ACCURATE */
    private String modelMode;

    /** 置信度阈值 */
    private Double confidenceThreshold;

    /** 推理精度：AUTO / FP32 / FP16 */
    private String inferencePrecision;

    /**
     * 识别时间
     */
    private LocalDateTime createTime;

    /**
     * 缺陷明细
     */
    private List<DetectDetailVO> details;
}
