package com.example.wooddetect.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI woodDetectOpenAPI() {
        return new OpenAPI().info(new Info()
                .title("木材表面缺陷检测 API")
                .version("v1")
                .description("上传识别、批量任务、历史查询、删除及导出接口"));
    }
}
