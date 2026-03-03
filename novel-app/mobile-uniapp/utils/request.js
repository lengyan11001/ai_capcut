const isH5 = typeof window !== "undefined" && typeof document !== "undefined";
const DEFAULT_BASE_URL = isH5 ? "http://localhost:8088" : "http://10.0.2.2:8088";

export async function request(url, method = "GET", data = null, withAuth = false) {
  const token =
    typeof uni !== "undefined" && uni.getStorageSync
      ? uni.getStorageSync("accessToken")
      : typeof localStorage !== "undefined"
        ? localStorage.getItem("accessToken")
        : "";
  const customBaseUrl =
    typeof uni !== "undefined" && uni.getStorageSync
      ? uni.getStorageSync("apiBaseUrl")
      : typeof localStorage !== "undefined"
        ? localStorage.getItem("apiBaseUrl")
        : "";
  const baseUrl = customBaseUrl || DEFAULT_BASE_URL;
  const header = {};
  if (withAuth && token) {
    header.Authorization = `Bearer ${token}`;
  }
  if (typeof uni === "undefined" || !uni.request) {
    const res = await fetch(`${baseUrl}${url}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...header
      },
      body: data ? JSON.stringify(data) : undefined
    });
    if (!res.ok) {
      throw new Error(`http ${res.status}`);
    }
    return res.json();
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
