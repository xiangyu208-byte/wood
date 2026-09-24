package com.example.wooddetect.util;

import com.example.wooddetect.dto.PythonDetectRequestDTO;
import com.example.wooddetect.dto.PythonDetectResponseDTO;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * 调用 Python 推理服
 * 把图片路径发给 Python
 * 接收 Python 返回结果
 * 转成 PythonDetectResponseDTO
 */
@Component
public class PythonDetectClient {

    /**
     * 从 application.yml 读取 Python 推理服务地址
     * 例如：http://127.0.0.1:8001/predict
     */
    @Value("${python.predict-url}")
    private String pythonPredictUrl;

    /**
     * 调用 Python 推理服务
     */
    public PythonDetectResponseDTO detect(String imagePath) {
        //Spring 提供的 HTTP 客户端工具，专门用来发送 HTTP 请求
        RestTemplate restTemplate = new RestTemplate();

        // 1. 组装请求体
        PythonDetectRequestDTO requestDTO = new PythonDetectRequestDTO();
        requestDTO.setImagePath(imagePath);

        // 2. 设置请求头
        HttpHeaders headers = new HttpHeaders();
        //设置请求头的 Content-Type 为 application/json
        headers.setContentType(MediaType.APPLICATION_JSON);

        // 3. 把请求体和请求头封装为 HttpEntity
        HttpEntity<PythonDetectRequestDTO> httpEntity = new HttpEntity<>(requestDTO, headers);

        // 4. 发送 POST 请求到 Python 推理服务
        ResponseEntity<PythonDetectResponseDTO> response = restTemplate.exchange(
                pythonPredictUrl,
                HttpMethod.POST,//指定发送 POST 请求
                httpEntity,
                PythonDetectResponseDTO.class//指定响应体的类型，RestTemplate 会自动把 Python 服务返回的 JSON 转换成这个 DTO 对象。
        );

        // 5. 获取响应体
        PythonDetectResponseDTO body = response.getBody();
        if (body == null) {
            throw new RuntimeException("Python 推理服务返回为空");
        }

        return body;
    }
}