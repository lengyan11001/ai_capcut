package com.novel.app.model;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "wallet_flow")
public class WalletFlowEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long userId;

    @Column(nullable = false)
    private Long deltaCoins;

    @Column(nullable = false)
    private Long balanceAfter;

    @Column(nullable = false, length = 32)
    private String bizType;

    @Column(nullable = false, length = 64)
    private String bizId;

    @Column(nullable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}
