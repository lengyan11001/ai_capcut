import { defineStore } from "pinia";
import { request } from "../utils/request";

function safeGetStorage(key) {
  if (typeof uni !== "undefined" && uni.getStorageSync) {
    return uni.getStorageSync(key);
  }
  if (typeof localStorage !== "undefined") {
    return localStorage.getItem(key) || "";
  }
  return "";
}

function safeSetStorage(key, value) {
  if (typeof uni !== "undefined" && uni.setStorageSync) {
    uni.setStorageSync(key, value);
    return;
  }
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(key, value);
  }
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    userId: null,
    nickname: "",
    accessToken: safeGetStorage("accessToken"),
    refreshToken: safeGetStorage("refreshToken")
  }),
  actions: {
    async smsLogin(phone, code) {
      const res = await request("/auth/sms-login", "POST", { phone, code });
      const data = res.data || {};
      this.userId = data.userId;
      this.nickname = data.nickname;
      this.accessToken = data.accessToken;
      this.refreshToken = data.refreshToken;
      safeSetStorage("accessToken", this.accessToken);
      safeSetStorage("refreshToken", this.refreshToken);
    }
  }
});
