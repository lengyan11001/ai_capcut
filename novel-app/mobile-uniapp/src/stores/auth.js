import { defineStore } from "pinia";
import { request } from "../utils/request";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    userId: null,
    nickname: "",
    accessToken: uni.getStorageSync("accessToken") || "",
    refreshToken: uni.getStorageSync("refreshToken") || ""
  }),
  actions: {
    async smsLogin(phone, code) {
      const res = await request("/auth/sms-login", "POST", { phone, code });
      const data = res.data || {};
      this.userId = data.userId;
      this.nickname = data.nickname;
      this.accessToken = data.accessToken;
      this.refreshToken = data.refreshToken;
      uni.setStorageSync("accessToken", this.accessToken);
      uni.setStorageSync("refreshToken", this.refreshToken);
    }
  }
});
