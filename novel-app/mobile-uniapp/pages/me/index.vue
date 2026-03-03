<template>
  <view class="page">
    <view class="card">
      <view class="title">我的账户</view>
      <view class="line">昵称：{{ authStore.nickname || "-" }}</view>
      <view class="line">书币余额：{{ walletStore.balanceCoins }}</view>
      <button type="primary" @click="goRecharge">去充值</button>
    </view>
  </view>
</template>

<script setup>
import { onMounted } from "vue";
import { useAuthStore } from "../../stores/auth";
import { useWalletStore } from "../../stores/wallet";

const authStore = useAuthStore();
const walletStore = useWalletStore();

onMounted(async () => {
  try {
    await walletStore.loadBalance();
  } catch (e) {
    uni.showToast({ title: "请先登录", icon: "none" });
    uni.navigateTo({ url: "/pages/login/index" });
  }
});

function goRecharge() {
  uni.navigateTo({ url: "/pages/recharge/index" });
}
</script>

<style scoped>
.page {
  padding: 24rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 22rpx;
}
.title {
  font-size: 34rpx;
  font-weight: 600;
  margin-bottom: 14rpx;
}
.line {
  margin-bottom: 10rpx;
}
</style>
