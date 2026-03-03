package com.novel.app.service;

import com.novel.app.model.WalletAccountEntity;
import com.novel.app.model.WalletFlowEntity;
import com.novel.app.repository.WalletAccountRepository;
import com.novel.app.repository.WalletFlowRepository;
import jakarta.transaction.Transactional;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class WalletService {
    private final WalletAccountRepository walletAccountRepository;
    private final WalletFlowRepository walletFlowRepository;

    public WalletService(WalletAccountRepository walletAccountRepository, WalletFlowRepository walletFlowRepository) {
        this.walletAccountRepository = walletAccountRepository;
        this.walletFlowRepository = walletFlowRepository;
    }

    public WalletAccountEntity getOrCreate(Long userId) {
        return walletAccountRepository.findByUserId(userId).orElseGet(() -> {
            WalletAccountEntity entity = new WalletAccountEntity();
            entity.setUserId(userId);
            return walletAccountRepository.save(entity);
        });
    }

    @Transactional
    public WalletAccountEntity addCoins(Long userId, Long coins, String bizType, String bizId) {
        WalletAccountEntity account = getOrCreate(userId);
        long newBalance = account.getBalanceCoins() + coins;
        account.setBalanceCoins(newBalance);
        account.setUpdatedAt(LocalDateTime.now());
        walletAccountRepository.save(account);

        WalletFlowEntity flow = new WalletFlowEntity();
        flow.setUserId(userId);
        flow.setDeltaCoins(coins);
        flow.setBalanceAfter(newBalance);
        flow.setBizType(bizType);
        flow.setBizId(bizId);
        walletFlowRepository.save(flow);
        return account;
    }

    public List<WalletFlowEntity> flows(Long userId) {
        return walletFlowRepository.findTop50ByUserIdOrderByCreatedAtDesc(userId);
    }
}
