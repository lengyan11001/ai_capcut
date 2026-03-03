package com.novel.app.repository;

import com.novel.app.model.BookShelfEntity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface BookShelfRepository extends JpaRepository<BookShelfEntity, Long> {
    List<BookShelfEntity> findByUserIdOrderByUpdatedAtDesc(Long userId);

    Optional<BookShelfEntity> findByUserIdAndBookId(Long userId, String bookId);
}
