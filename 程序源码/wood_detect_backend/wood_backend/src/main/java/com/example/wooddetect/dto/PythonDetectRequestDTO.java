package com.example.wooddetect.dto;

import lombok.Data;

/**
 * Spring Boot 发给 Python 推理服务的请求体。
 * 最简单、最稳的方式就是只传一项：图片的路径，python根据这个路径读取照片
 */
@Data
public class PythonDetectRequestDTO {
    /**
     * 原图在服务器磁盘上的真实路径
     */
    private String imagePath;
}