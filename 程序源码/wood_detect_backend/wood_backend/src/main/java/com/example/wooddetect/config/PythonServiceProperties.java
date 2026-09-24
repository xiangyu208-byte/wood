package com.example.wooddetect.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.time.Duration;

@Data
@Component
@ConfigurationProperties(prefix = "python")
public class PythonServiceProperties {

    private String predictUrl;

    private Duration connectTimeout = Duration.ofSeconds(3);

    private Duration readTimeout = Duration.ofSeconds(120);

    private int maxAttempts = 2;

    private Duration retryDelay = Duration.ofMillis(500);
}
