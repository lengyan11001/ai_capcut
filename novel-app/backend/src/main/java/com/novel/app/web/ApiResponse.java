package com.novel.app.web;

public record ApiResponse<T>(int code, String message, T data) {
    public static <T> ApiResponse<T> ok(T data) {
        return new ApiResponse<>(0, "ok", data);
    }

    public static <T> ApiResponse<T> fail(String message) {
        return new ApiResponse<>(1, message, null);
    }
}
