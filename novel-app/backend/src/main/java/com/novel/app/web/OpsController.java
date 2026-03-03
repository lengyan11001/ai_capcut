package com.novel.app.web;

import com.novel.app.service.OpsService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/ops")
public class OpsController {
    private final OpsService opsService;

    public OpsController(OpsService opsService) {
        this.opsService = opsService;
    }

    @GetMapping("/banners")
    public ApiResponse<?> banners() {
        return ApiResponse.ok(opsService.banners());
    }

    @GetMapping("/channels")
    public ApiResponse<?> channels() {
        return ApiResponse.ok(opsService.channels());
    }
}
