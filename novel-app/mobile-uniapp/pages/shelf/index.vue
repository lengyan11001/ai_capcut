<template>
  <view class="page">
    <view v-for="item in shelfStore.list" :key="item.id" class="book-card">
      <view class="title">{{ item.bookTitle }}</view>
      <view class="actions">
        <button size="mini" @click="openReader(item.bookId)">阅读</button>
        <button size="mini" type="warn" @click="remove(item.bookId)">移除</button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onMounted } from "vue";
import { useShelfStore } from "../../stores/shelf";

const shelfStore = useShelfStore();

onMounted(async () => {
  await shelfStore.loadShelf();
});

function openReader(bookId) {
  uni.navigateTo({ url: `/pages/reader/index?bookId=${bookId}` });
}

async function remove(bookId) {
  await shelfStore.removeShelf(bookId);
}
</script>

<style scoped>
.page {
  padding: 24rpx;
}
.book-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 16rpx;
}
.title {
  font-size: 30rpx;
  margin-bottom: 14rpx;
}
.actions {
  display: flex;
  gap: 12rpx;
}
</style>
