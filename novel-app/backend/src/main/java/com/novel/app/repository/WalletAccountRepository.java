package com.novel.app.repository;

import com.novel.app.model.WalletAccountEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface WalletAccountRepository extends JpaRepository<WalletAccountEntity, Long> {
    Optional<WalletAccountEntity> findByUserId(Long userId);
}
