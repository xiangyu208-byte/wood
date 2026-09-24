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