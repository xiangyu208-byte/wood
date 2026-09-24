package com.example.wooddetect.common;

import lombok.Data;

/**
 *这是统一返回结果类。
 *后端接口不会直接裸返回数据，而是统一包装成这种格式
 * 这是统一返回结果类。
 * 以后你的后端接口不会直接裸返回数据，而是统一包装成这种格式
 * {
 *   "code": 200,
 *   "message": "success",
 *   "data": ...
 * }
 * 静态方法属于类本身，不用创建对象就可以被调用
 * @param <T>
 */
@Data
public class Result<T> {

    private Integer code;//常见约定 200成功 500失败
    private String message;//返回提示信息
    private T data;//接口真正返回的数据

    public static <T> Result<T> success(T data) {
        Result<T> result = new Result<>();
        result.setCode(200);
        result.setMessage("success");
        result.setData(data);
        return result;
    }

    public static <T> Result<T> success(String message, T data) {
        Result<T> result = new Result<>();
        result.setCode(200);
        result.setMessage(message);
        result.setData(data);
        return result;
    }

    public static <T> Result<T> fail(String message) {
        Result<T> result = new Result<>();
        result.setCode(500);
        result.setMessage(message);
        result.setData(null);
        return result;
    }
}