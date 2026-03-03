const isH5 = typeof window !== "undefined" && typeof document !== "undefined";
const DEFAULT_BASE_URL = isH5 ? "http://localhost:8088" : "http://10.0.2.2:8088";

export async function request(url, method = "GET", data = null, withAuth = false) {
  const token = uni.getStorageSync("accessToken");
  const customBaseUrl = uni.getStorageSync("apiBaseUrl");
  const baseUrl = customBaseUrl || DEFAULT_BASE_URL;
  const header = {};
  if (withAuth && token) {
    header.Authorization = `Bearer ${token}`;
  }
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${baseUrl}${url}`,
      method,
      data,
      header,
      timeout: 8000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
        reject(new Error(`http ${res.statusCode}`));
      },
      fail: (e) => reject(e)
    });
  });
}
