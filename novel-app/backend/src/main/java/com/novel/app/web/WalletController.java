package com.novel.app.web;

import com.novel.app.service.WalletService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/wallet")
public class WalletController {
    private final WalletService walletService;
    private final AuthHeaderSupport authHeaderSupport;

    public WalletController(WalletService walletService, AuthHeaderSupport authHeaderSupport) {
        this.walletService = walletService;
        this.authHeaderSupport = authHeaderSupport;
    }

    @GetMapping("/balance")
    public ApiResponse<?> balance(@RequestHeader("Authorization") String authorization) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        var account = walletService.getOrCreate(userId);
        return ApiResponse.ok(Map.of("userId", userId, "balanceCoins", account.getBalanceCoins()));
    }

    @GetMapping("/flows")
    public ApiResponse<?> flows(@RequestHeader("Authorization") String authorization) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        return ApiResponse.ok(walletService.flows(userId));
    }
}
