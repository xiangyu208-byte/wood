package com.example.wooddetect.vo;

import lombok.Data;

@Data
public class DetectDetailVO {

    /**
     * 缺陷类别名称
     */
    private String className;

    /**
     * 置信度
     */
    private Double confidence;

    /**
     * 检测框坐标
     */
    private Integer x1;
    private Integer y1;
    private Integer x2;
    private Integer y2;
}