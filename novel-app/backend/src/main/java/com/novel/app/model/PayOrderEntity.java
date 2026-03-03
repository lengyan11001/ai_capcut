package com.novel.app.model;

import jakarta.persistence.*;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "pay_order")
public class PayOrderEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 64)
    private String orderNo;

    @Column(nullable = false)
    private Long userId;

    @Column(nullable = false)
    private Long coinAmount;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal cashAmount;

    @Column(nullable = false, length = 20)
    private String channel;

    @Column(nullable = false, length = 20)
    private String status = "CREATED";

    @Lob
    private String callbackPayload;

    @Column(nullable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    private LocalDateTime paidAt;
}
