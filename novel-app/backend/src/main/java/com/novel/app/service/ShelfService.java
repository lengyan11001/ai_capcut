package com.novel.app.service;

import com.novel.app.model.BookShelfEntity;
import com.novel.app.repository.BookShelfRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class ShelfService {
    private final BookShelfRepository bookShelfRepository;

    public ShelfService(BookShelfRepository bookShelfRepository) {
        this.bookShelfRepository = bookShelfRepository;
    }

    public List<BookShelfEntity> list(Long userId) {
        return bookShelfRepository.findByUserIdOrderByUpdatedAtDesc(userId);
    }

    public void add(Long userId, String bookId, String bookTitle) {
        BookShelfEntity entity = bookShelfRepository.findByUserIdAndBookId(userId, bookId).orElseGet(BookShelfEntity::new);
        entity.setUserId(userId);
        entity.setBookId(bookId);
        entity.setBookTitle(bookTitle);
        entity.setUpdatedAt(LocalDateTime.now());
        bookShelfRepository.save(entity);
    }

    public void remove(Long userId, String bookId) {
        bookShelfRepository.findByUserIdAndBookId(userId, bookId).ifPresent(bookShelfRepository::delete);
    }
}
