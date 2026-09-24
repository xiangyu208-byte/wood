package com.example.wooddetect.common;

import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 是全局异常处理器。
 * 后端项目里只要出现异常，它都可以统一捕获，然后返回统一格式的错误信息。
 * @RestControllerAdvice 标记这是一个全局控制器增强类，
 * 会拦截所有 @RestController 中抛出的异常,最终返回的结果会自动序列化为 JSON
 * @ExceptionHandler 标记这是一个异常处理方法；
 * Exception.class 表示捕获所有类型的异常
 *
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    public Result<String> handleException(Exception e) {
        e.printStackTrace();
        return Result.fail("系统异常：" + e.getMessage());
    }
}