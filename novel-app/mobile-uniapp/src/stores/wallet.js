import { defineStore } from "pinia";
import { request } from "../utils/request";

export const useWalletStore = defineStore("wallet", {
  state: () => ({
    balanceCoins: 0,
    orders: []
  }),
  actions: {
    async loadBalance() {
      const res = await request("/wallet/balance", "GET", null, true);
      this.balanceCoins = res.data?.balanceCoins || 0;
    },
    async createRecharge(coinAmount, cashAmount) {
      return request(
        "/pay/create",
        "POST",
        {
          coinAmount,
          cashAmount,
          channel: "mockpay"
        },
        true
      );
    },
    async loadOrders() {
      const res = await request("/pay/orders", "GET", null, true);
      this.orders = res.data || [];
    }
  }
});
