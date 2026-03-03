package com.novel.app.web;

import com.novel.app.model.PayOrderEntity;
import com.novel.app.service.PayService;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.Map;

@RestController
@RequestMapping("/pay")
public class PayController {
    private final PayService payService;
    private final AuthHeaderSupport authHeaderSupport;

    public PayController(PayService payService, AuthHeaderSupport authHeaderSupport) {
        this.payService = payService;
        this.authHeaderSupport = authHeaderSupport;
    }

    @PostMapping("/create")
    public ApiResponse<?> create(@RequestHeader("Authorization") String authorization, @RequestBody Map<String, Object> body) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        Long coinAmount = Long.parseLong(String.valueOf(body.get("coinAmount")));
        BigDecimal cashAmount = new BigDecimal(String.valueOf(body.get("cashAmount")));
        String channel = String.valueOf(body.getOrDefault("channel", "mockpay"));
        PayOrderEntity order = payService.createOrder(userId, coinAmount, cashAmount, channel);
        String mockSign = payService.buildCallbackSign(order.getOrderNo());
        return ApiResponse.ok(Map.of(
                "orderNo", order.getOrderNo(),
                "status", order.getStatus(),
                "mockCallbackSign", mockSign
        ));
    }

    @PostMapping("/callback/{channel}")
    public ApiResponse<?> callback(@PathVariable String channel, @RequestBody Map<String, String> body) {
        boolean ok = payService.callback(channel, body.get("orderNo"), body.get("sign"), String.valueOf(body));
        return ok ? ApiResponse.ok(Map.of("success", true)) : ApiResponse.fail("invalid sign");
    }

    @GetMapping("/orders")
    public ApiResponse<?> orders(@RequestHeader("Authorization") String authorization) {
        Long userId = authHeaderSupport.requiredUserId(authorization);
        return ApiResponse.ok(payService.userOrders(userId));
    }
}
