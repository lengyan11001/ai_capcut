package com.novel.app.repository;

import com.novel.app.model.PayOrderEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface PayOrderRepository extends JpaRepository<PayOrderEntity, Long> {
    Optional<PayOrderEntity> findByOrderNo(String orderNo);

    List<PayOrderEntity> findTop50ByUserIdOrderByCreatedAtDesc(Long userId);

    List<PayOrderEntity> findTop100ByStatusOrderByCreatedAtAsc(String status);
}
