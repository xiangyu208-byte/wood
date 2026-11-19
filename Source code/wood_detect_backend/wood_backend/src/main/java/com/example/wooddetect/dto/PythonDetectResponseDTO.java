package com.example.wooddetect.dto;

import lombok.Data;

import java.util.List;

/**
 * python推理返回给Springboot的结果
 */
@Data
public class PythonDetectResponseDTO {

    /**
     * Python 推理是否成功
     */
    private Boolean success;

    /**
     * 结果图在磁盘上的真实路径
     */
    private String resultImagePath;

    /**
     * 结果图给前端访问的 URL
     */
    private String resultImageUrl;

    /**
     * 检测到的目标总数
     */
    private Integer totalCount;

    /** 模型权重版本，默认由文件名和 SHA-256 短哈希组成。 */
    private String modelVersion;

    /** 实际执行模式：FAST_WHOLE / STANDARD_WHOLE / ADAPTIVE_TILED / TILED_ACCURATE */
    private String actualMode;

    /** 模式选择原因 */
    private String decisionReason;

    /** 包含图像预处理、模型推理、NMS 和绘图的总耗时 */
    private Long inferenceDurationMs;

    /** 实际推理区域数量，整图为 1 */
    private Integer tileCount;

    private Integer imageWidth;
    private Integer imageHeight;

    /**
     * 检测明细列表
     */
    private List<DetectItemDTO> details;

    @Data
    public static class DetectItemDTO {

        /**
         * 缺陷类别名称
         */
        private String className;

        /**
         * 置信度
         */
        private Double confidence;

        /**
         * 检测框左上角坐标
         */
        private Integer x1;
        private Integer y1;

        /**
         * 检测框右下角坐标
         */
        private Integer x2;
        private Integer y2;
    }
}
