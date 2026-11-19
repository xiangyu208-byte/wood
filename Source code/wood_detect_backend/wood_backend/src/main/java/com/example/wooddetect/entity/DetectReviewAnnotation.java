package com.example.wooddetect.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("detect_review_annotation")
public class DetectReviewAnnotation {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long recordId;
    private Long originalDetailId;
    private String className;
    private Double confidence;
    private Integer x1;
    private Integer y1;
    private Integer x2;
    private Integer y2;
    private String sourceType;
    private LocalDateTime createTime;
}
