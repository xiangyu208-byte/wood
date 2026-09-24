package com.example.wooddetect.common;

import org.springframework.http.HttpStatus;

public class InferenceServiceException extends BusinessException {
    public InferenceServiceException(String message) {
        super(HttpStatus.SERVICE_UNAVAILABLE, message);
    }

    public InferenceServiceException(String message, Throwable cause) {
        super(HttpStatus.SERVICE_UNAVAILABLE, message, cause);
    }
}
