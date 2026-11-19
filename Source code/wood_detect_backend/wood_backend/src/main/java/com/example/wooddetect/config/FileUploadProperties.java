package com.example.wooddetect.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 把 application.yml 里的文件上传配置读取出来
 */
@Data
@Component
@ConfigurationProperties(prefix = "file")//读取yml文件里的值
public class FileUploadProperties {

    private String uploadPath;

    private String accessUrlPrefix;

    private List<String> allowedExtensions = List.of("jpg", "jpeg", "png", "bmp");

    private int maxWidth = 10000;

    private int maxHeight = 10000;

    private long maxPixels = 40_000_000L;

    private int maxBatchSize = 50;
}
