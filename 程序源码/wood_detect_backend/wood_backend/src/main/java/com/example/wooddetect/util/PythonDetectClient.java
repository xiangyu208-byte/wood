package com.example.wooddetect.util;

import com.example.wooddetect.common.InferenceServiceException;
import com.example.wooddetect.config.PythonServiceProperties;
import com.example.wooddetect.dto.PythonDetectRequestDTO;
import com.example.wooddetect.dto.PythonDetectResponseDTO;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.client.RestTemplate;

@Component
public class PythonDetectClient {

    private static final Logger log = LoggerFactory.getLogger(PythonDetectClient.class);

    private final PythonServiceProperties properties;
    private final RestTemplate restTemplate;

    public PythonDetectClient(PythonServiceProperties properties) {
        this.properties = properties;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.getConnectTimeout());
        factory.setReadTimeout(properties.getReadTimeout());
        this.restTemplate = new RestTemplate(factory);
    }

    public PythonDetectResponseDTO detect(String imagePath) {
        PythonDetectRequestDTO request = new PythonDetectRequestDTO();
        request.setImagePath(imagePath);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<PythonDetectRequestDTO> entity = new HttpEntity<>(request, headers);

        int attempts = Math.max(1, properties.getMaxAttempts());
        Exception lastError = null;

        for (int attempt = 1; attempt <= attempts; attempt++) {
            try {
                ResponseEntity<PythonDetectResponseDTO> response = restTemplate.exchange(
                        properties.getPredictUrl(), HttpMethod.POST, entity, PythonDetectResponseDTO.class);
                PythonDetectResponseDTO body = response.getBody();
                if (body == null) {
                    throw new InferenceServiceException("推理服务返回空响应");
                }
                return body;
            } catch (RestClientResponseException e) {
                lastError = e;
                if (e.getStatusCode().is4xxClientError()) {
                    throw new InferenceServiceException("推理服务拒绝请求，HTTP " + e.getStatusCode().value(), e);
                }
                log.warn("推理服务第 {}/{} 次调用失败，HTTP {}", attempt, attempts, e.getStatusCode().value());
            } catch (ResourceAccessException e) {
                lastError = e;
                log.warn("推理服务第 {}/{} 次连接失败: {}", attempt, attempts, e.getMessage());
            } catch (InferenceServiceException e) {
                throw e;
            } catch (Exception e) {
                lastError = e;
                log.warn("推理服务第 {}/{} 次调用异常: {}", attempt, attempts, e.getMessage());
            }

            if (attempt < attempts) {
                try {
                    Thread.sleep(Math.max(0, properties.getRetryDelay().toMillis()));
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    throw new InferenceServiceException("推理调用被中断", e);
                }
            }
        }

        throw new InferenceServiceException("推理服务暂时不可用，已重试 " + attempts + " 次", lastError);
    }
}
