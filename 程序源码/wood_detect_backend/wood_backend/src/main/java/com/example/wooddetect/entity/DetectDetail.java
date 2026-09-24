package com.example.wooddetect.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 一次检测出来个类别的明细
 */
@Data
@TableName("detect_detail")//可以不要，但若类名和表明不一样要写
public class DetectDetail {

    //这个注解表示这个是数据库中的主键字段，auto表示为自增
    @TableId(type = IdType.AUTO)
    private Long id;

    private Long recordId;

    private String className;

    private Double confidence;

    private Integer x1;

    private Integer y1;

    private Integer x2;

    private Integer y2;

    private LocalDateTime createTime;
}