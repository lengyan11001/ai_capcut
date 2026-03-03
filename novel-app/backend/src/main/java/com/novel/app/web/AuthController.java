package com.novel.app.web;

import com.novel.app.model.UserEntity;
import com.novel.app.service.AuthService;
import jakarta.validation.constraints.NotBlank;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Validated
@RestController
@RequestMapping("/auth")
public class AuthController {
    private final AuthService authService;
    private final AuthHeaderSupport authHeaderSupport;

    public AuthController(AuthService authService, AuthHeaderSupport authHeaderSupport) {
        this.authService = authService;
        this.authHeaderSupport = authHeaderSupport;
    }

    @PostMapping("/sms-login")
    public ApiResponse<?> smsLogin(@RequestBody Map<String, String> body) {
        return ApiResponse.ok(authService.smsLogin(body.get("phone"), body.get("code")));
    }

    @PostMapping("/refresh")
    public ApiResponse<?> refresh(@RequestBody Map<String, String> body) {
        return ApiResponse.ok(authService.refresh(body.get("refreshToken")));
    }

    @GetMapping("/profile")
    public ApiResponse<UserEntity> profile(@RequestHeader("Authorization") @NotBlank String authorization) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        return ApiResponse.ok(authService.profile(userId));
    }
}
