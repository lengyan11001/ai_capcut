<template>
  <view class="page">
    <view class="title">小说 App 登录</view>
    <input v-model="phone" class="input" placeholder="手机号" />
    <input v-model="code" class="input" placeholder="验证码（测试用 123456）" />
    <button type="primary" @click="onLogin">登录</button>
  </view>
</template>

<script setup>
import { ref } from "vue";
import { useAuthStore } from "../../stores/auth";

const authStore = useAuthStore();
const phone = ref("13800138000");
const code = ref("123456");

async function onLogin() {
  try {
    await authStore.smsLogin(phone.value, code.value);
    uni.switchTab({ url: "/pages/home/index" });
  } catch (e) {
    uni.showToast({ title: "登录失败", icon: "none" });
  }
}
</script>

<style scoped>
.page {
  padding: 32rpx;
}
.title {
  margin-bottom: 24rpx;
  font-size: 40rpx;
  font-weight: 600;
}
.input {
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
  padding: 20rpx;
}
</style>
