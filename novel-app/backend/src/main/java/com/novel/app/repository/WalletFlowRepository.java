package com.novel.app.repository;

import com.novel.app.model.WalletFlowEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface WalletFlowRepository extends JpaRepository<WalletFlowEntity, Long> {
    List<WalletFlowEntity> findTop50ByUserIdOrderByCreatedAtDesc(Long userId);
}
