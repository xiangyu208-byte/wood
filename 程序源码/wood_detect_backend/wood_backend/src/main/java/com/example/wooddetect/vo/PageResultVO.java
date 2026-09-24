package com.example.wooddetect.vo;

import lombok.Data;

import java.util.List;

@Data
public class PageResultVO<T> {

    /**
     * 当前页数据
     */
    private List<T> records;

    /**
     * 总记录数
     */
    private Long total;

    /**
     * 当前页码
     */
    private Integer page;

    /**
     * 每页大小
     */
    private Integer size;
}