import { defineStore } from "pinia";
import { request } from "../utils/request";

export const useContentStore = defineStore("content", {
  state: () => ({
    feed: [],
    currentBook: null,
    chapters: []
  }),
  actions: {
    async loadFeed() {
      const res = await request("/home/feed");
      this.feed = res.data || [];
    },
    async loadBook(bookId) {
      const [bookRes, chapterRes] = await Promise.all([request(`/books/${bookId}`), request(`/books/${bookId}/chapters`)]);
      this.currentBook = bookRes.data;
      this.chapters = chapterRes.data || [];
    },
    async search(keyword) {
      const res = await request(`/search/result?keyword=${encodeURIComponent(keyword)}`);
      return res.data || [];
    }
  }
});
