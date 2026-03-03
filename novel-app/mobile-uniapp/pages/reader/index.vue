<template>
  <view class="page">
    <view class="title">{{ readerStore.chapterTitle || "阅读器" }}</view>
    <scroll-view class="content" scroll-y @scroll="onScroll">
      <text>{{ readerStore.content }}</text>
    </scroll-view>
    <view class="toolbar">
      <button size="mini" @click="save">保存进度</button>
    </view>
  </view>
</template>

<script setup>
import { onLoad } from "@dcloudio/uni-app";
import { useReaderStore } from "../../stores/reader";
import { useContentStore } from "../../stores/content";

const readerStore = useReaderStore();
const contentStore = useContentStore();
let bookId = "";

onLoad(async (query) => {
  bookId = query.bookId || "bk_1001";
  try {
    await contentStore.loadBook(bookId);
    const firstChapter = contentStore.chapters[0];
    if (firstChapter) {
      await readerStore.openChapter(firstChapter.chapterId);
    }
  } catch (e) {
    uni.showToast({ title: "章节加载失败", icon: "none" });
  }
});

function onScroll(e) {
  readerStore.offsetChar = Math.floor((e.detail.scrollTop || 0) / 2);
}

async function save() {
  await readerStore.saveProgress(bookId);
  uni.showToast({ title: "已保存", icon: "success" });
}
</script>

<style scoped>
.page {
  padding: 24rpx;
}
.title {
  font-size: 34rpx;
  font-weight: 600;
  margin-bottom: 14rpx;
}
.content {
  height: 72vh;
  line-height: 1.8;
  background: #fff;
  border-radius: 16rpx;
  padding: 22rpx;
}
.toolbar {
  margin-top: 20rpx;
}
</style>
