package com.example.wooddetect.vo;

import lombok.Data;

@Data
public class ReviewAnnotationVO {
    private Long id;
    private Long originalDetailId;
    private String className;
    private Double confidence;
    private Integer x1;
    private Integer y1;
    private Integer x2;
    private Integer y2;
    private String sourceType;
}
