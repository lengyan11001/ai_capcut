import { defineStore } from "pinia";
import { request } from "../utils/request";

export const useReaderStore = defineStore("reader", {
  state: () => ({
    chapterId: "",
    chapterTitle: "",
    content: "",
    offsetChar: 0
  }),
  actions: {
    async openChapter(chapterId) {
      const res = await request(`/chapters/${chapterId}/content`);
      const data = res.data || {};
      this.chapterId = chapterId;
      this.chapterTitle = data.title || "";
      this.content = data.content || "";
    },
    async saveProgress(bookId) {
      await request(
        "/reading/progress/save",
        "POST",
        {
          bookId,
          chapterId: this.chapterId,
          offsetChar: this.offsetChar
        },
        true
      );
    }
  }
});
