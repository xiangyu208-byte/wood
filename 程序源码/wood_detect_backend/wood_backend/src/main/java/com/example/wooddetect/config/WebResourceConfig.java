package com.example.wooddetect.config;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 你本地磁盘上的上传目录映射成 Spring Boot 可访问的静态资源。
 * @Configuration 标记这是一个配置类，Spring 启动时会加载并执行其中的配置逻辑
 *
 */
@Configuration
public class WebResourceConfig implements WebMvcConfigurer {

    @Autowired
    private FileUploadProperties fileUploadProperties;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        String accessUrlPrefix = fileUploadProperties.getAccessUrlPrefix();
        String uploadPath = fileUploadProperties.getUploadPath();

        if (!accessUrlPrefix.endsWith("/")) {
            accessUrlPrefix = accessUrlPrefix + "/";
        }

        uploadPath = uploadPath.replace("\\", "/");
        if (!uploadPath.endsWith("/")) {
            uploadPath = uploadPath + "/";
        }

        registry.addResourceHandler(accessUrlPrefix + "**")
                .addResourceLocations("file:" + uploadPath);
    }
}