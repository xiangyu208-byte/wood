package com.example.wooddetect.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 把 application.yml 里的文件上传配置读取出来
 */
@Data
@Component
@ConfigurationProperties(prefix = "file")//读取yml文件里的值
public class FileUploadProperties {

    private String uploadPath;

    private String accessUrlPrefix;
}