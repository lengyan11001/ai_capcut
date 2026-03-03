package com.novel.app.model;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "wallet_account")
public class WalletAccountEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true)
    private Long userId;

    @Column(nullable = false)
    private Long balanceCoins = 0L;

    @Column(nullable = false)
    private LocalDateTime updatedAt = LocalDateTime.now();
}
