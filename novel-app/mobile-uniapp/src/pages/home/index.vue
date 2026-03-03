<template>
  <view class="page">
    <input v-model="keyword" class="search" placeholder="搜书名/作者" @confirm="onSearch" />
    <view v-if="resultMode">
      <view class="section-title">搜索结果</view>
      <view v-for="item in resultList" :key="item.bookId" class="book-card">
        <view class="title">{{ item.title }}</view>
        <view class="desc">{{ item.category }} · {{ item.author }}</view>
      </view>
    </view>
    <view v-else>
      <view class="section-title">推荐</view>
      <view v-for="item in contentStore.feed" :key="item.bookId" class="book-card" @click="goReader(item)">
        <view class="title">{{ item.title }}</view>
        <view class="desc">{{ item.category }} · {{ item.author }}</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useContentStore } from "../../stores/content";
import { useShelfStore } from "../../stores/shelf";

const contentStore = useContentStore();
const shelfStore = useShelfStore();
const keyword = ref("");
const resultMode = ref(false);
const resultList = ref([]);

onMounted(async () => {
  try {
    await contentStore.loadFeed();
  } catch (e) {
    uni.showToast({ title: "加载失败", icon: "none" });
  }
});

async function onSearch() {
  if (!keyword.value) {
    resultMode.value = false;
    return;
  }
  try {
    resultList.value = await contentStore.search(keyword.value);
    resultMode.value = true;
  } catch (e) {
    uni.showToast({ title: "搜索失败", icon: "none" });
  }
}

async function goReader(book) {
  try {
    await shelfStore.addShelf(book);
    uni.navigateTo({ url: `/pages/reader/index?bookId=${book.bookId}` });
  } catch (e) {
    uni.showToast({ title: "操作失败", icon: "none" });
  }
}
</script>

<style scoped>
.page {
  padding: 24rpx;
}
.search {
  background: #fff;
  border-radius: 12rpx;
  padding: 18rpx;
}
.section-title {
  margin: 20rpx 0 12rpx;
  font-size: 32rpx;
  font-weight: 600;
}
.book-card {
  background: #fff;
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 14rpx;
}
.title {
  font-size: 30rpx;
  font-weight: 600;
}
.desc {
  color: #666;
  margin-top: 8rpx;
}
</style>
