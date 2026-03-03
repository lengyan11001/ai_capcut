package com.novel.app.web;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.Map;

@RestController
public class SystemController {
    @GetMapping("/healthz")
    public ApiResponse<?> healthz() {
        return ApiResponse.ok(Map.of("status", "UP", "time", LocalDateTime.now().toString()));
    }
}
