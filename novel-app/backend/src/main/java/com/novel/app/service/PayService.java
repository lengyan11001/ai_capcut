package com.novel.app.service;

import com.novel.app.config.NovelProperties;
import com.novel.app.model.PayOrderEntity;
import com.novel.app.repository.PayOrderRepository;
import jakarta.transaction.Transactional;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Service
public class PayService {
    private final PayOrderRepository payOrderRepository;
    private final WalletService walletService;
    private final NovelProperties novelProperties;

    public PayService(PayOrderRepository payOrderRepository, WalletService walletService, NovelProperties novelProperties) {
        this.payOrderRepository = payOrderRepository;
        this.walletService = walletService;
        this.novelProperties = novelProperties;
    }

    public PayOrderEntity createOrder(Long userId, Long coinAmount, BigDecimal cashAmount, String channel) {
        PayOrderEntity entity = new PayOrderEntity();
        entity.setOrderNo("NO" + UUID.randomUUID().toString().replace("-", "").substring(0, 20));
        entity.setUserId(userId);
        entity.setCoinAmount(coinAmount);
        entity.setCashAmount(cashAmount);
        entity.setChannel(channel);
        return payOrderRepository.save(entity);
    }

    @Transactional
    public boolean callback(String channel, String orderNo, String sign, String payload) {
        String expected = buildCallbackSign(orderNo);
        if (!expected.equals(sign)) {
            return false;
        }
        PayOrderEntity order = payOrderRepository.findByOrderNo(orderNo).orElseThrow();
        if ("PAID".equals(order.getStatus())) {
            return true;
        }
        order.setStatus("PAID");
        order.setChannel(channel);
        order.setCallbackPayload(payload);
        order.setPaidAt(LocalDateTime.now());
        payOrderRepository.save(order);
        walletService.addCoins(order.getUserId(), order.getCoinAmount(), "PAY_RECHARGE", order.getOrderNo());
        return true;
    }

    public List<PayOrderEntity> userOrders(Long userId) {
        return payOrderRepository.findTop50ByUserIdOrderByCreatedAtDesc(userId);
    }

    public String buildCallbackSign(String orderNo) {
        return Integer.toHexString((orderNo + "|" + novelProperties.getPayment().getCallbackSecret()).hashCode());
    }

    @Scheduled(fixedDelay = 60000)
    public void reconcileCreatedOrders() {
        List<PayOrderEntity> list = payOrderRepository.findTop100ByStatusOrderByCreatedAtAsc("CREATED");
        LocalDateTime expireBefore = LocalDateTime.now().minusMinutes(30);
        for (PayOrderEntity order : list) {
            if (order.getCreatedAt().isBefore(expireBefore)) {
                order.setStatus("CLOSED");
                payOrderRepository.save(order);
            }
        }
    }
}
