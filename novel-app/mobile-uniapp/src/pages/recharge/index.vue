<template>
  <view class="page">
    <view class="card" v-for="item in plans" :key="item.coinAmount">
      <view>{{ item.coinAmount }} 书币</view>
      <view>￥{{ item.cashAmount }}</view>
      <button size="mini" type="primary" @click="buy(item)">充值</button>
    </view>
  </view>
</template>

<script setup>
import { useWalletStore } from "../../stores/wallet";

const walletStore = useWalletStore();
const plans = [
  { coinAmount: 1000, cashAmount: "10.00" },
  { coinAmount: 3000, cashAmount: "28.00" },
  { coinAmount: 6800, cashAmount: "60.00" }
];

async function buy(item) {
  const res = await walletStore.createRecharge(item.coinAmount, item.cashAmount);
  uni.showModal({
    title: "模拟支付",
    content: `订单号：${res.data.orderNo}\n请调用 /pay/callback/mockpay 完成入账。`,
    showCancel: false
  });
}
</script>

<style scoped>
.page {
  padding: 24rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 20rpx;
  margin-bottom: 14rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
