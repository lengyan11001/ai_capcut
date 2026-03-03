import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 20,
  duration: "60s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<800"]
  }
};

export default function () {
  const feedRes = http.get("http://localhost:8088/home/feed");
  check(feedRes, { "feed status is 200": (r) => r.status === 200 });

  const chapterRes = http.get("http://localhost:8088/chapters/bk_1001_ch_1/content");
  check(chapterRes, { "chapter status is 200": (r) => r.status === 200 });
  sleep(1);
}
