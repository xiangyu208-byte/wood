package com.example.wooddetect;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 这是一个 Spring Boot 启动类
 * 开启自动配置
 * 自动扫描当前包及其子包下的组件
 * 核心作用是扫描并加载带有 @Controller/@Service/@Component/@Repository 等注解的类
 */
@SpringBootApplication
@MapperScan("com.example.wooddetect.mapper")//指定扫描mapper包
public class WoodDetectApplication {

    public static void main(String[] args) {
        SpringApplication.run(WoodDetectApplication.class, args);
    }
}