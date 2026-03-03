<template>
  <div class="layout">
    <h1>小说后台管理（MVP）</h1>

    <section class="card">
      <h2>运营位管理</h2>
      <button @click="loadOps">刷新运营位</button>
      <div class="row">
        <div>
          <h3>Banner</h3>
          <pre>{{ banners }}</pre>
        </div>
        <div>
          <h3>频道位</h3>
          <pre>{{ channels }}</pre>
        </div>
      </div>
    </section>

    <section class="card">
      <h2>订单查询</h2>
      <input v-model="token" placeholder="粘贴用户 accessToken" />
      <button @click="loadOrders">查询订单</button>
      <pre>{{ orders }}</pre>
    </section>

    <section class="card">
      <h2>用户查询</h2>
      <button @click="loadUser">查询用户信息</button>
      <pre>{{ userProfile }}</pre>
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { fetchBanners, fetchChannels, fetchOrderList, fetchUserProfile } from "./api";

const token = ref("");
const banners = ref([]);
const channels = ref([]);
const orders = ref([]);
const userProfile = ref(null);

async function loadOps() {
  const [b, c] = await Promise.all([fetchBanners(), fetchChannels()]);
  banners.value = b.data || [];
  channels.value = c.data || [];
}

async function loadOrders() {
  if (!token.value) return;
  const res = await fetchOrderList(token.value);
  orders.value = res.data || [];
}

async function loadUser() {
  if (!token.value) return;
  const res = await fetchUserProfile(token.value);
  userProfile.value = res.data || null;
}
</script>

<style scoped>
.layout {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px;
  font-family: Arial, sans-serif;
}
.card {
  border: 1px solid #ddd;
  border-radius: 12px;
  margin-top: 16px;
  padding: 16px;
  background: #fff;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
input {
  min-width: 360px;
  margin-right: 8px;
  padding: 8px;
}
pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 8px;
  overflow: auto;
}
</style>
