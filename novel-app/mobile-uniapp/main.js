import { createSSRApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";

const app = createSSRApp(App);
app.use(createPinia());
app.mount("#app");
