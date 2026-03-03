import { defineStore } from "pinia";
import { request } from "../utils/request";

export const useShelfStore = defineStore("shelf", {
  state: () => ({
    list: []
  }),
  actions: {
    async loadShelf() {
      const res = await request("/shelf/list", "GET", null, true);
      this.list = res.data || [];
    },
    async addShelf(book) {
      await request("/shelf/add", "POST", { bookId: book.bookId, bookTitle: book.title }, true);
      await this.loadShelf();
    },
    async removeShelf(bookId) {
      await request("/shelf/remove", "POST", { bookId }, true);
      await this.loadShelf();
    }
  }
});
