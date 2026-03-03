const BASE_URL = "http://localhost:8088";

async function api(url, method = "GET", data) {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (data) {
    options.body = JSON.stringify(data);
  }
  const res = await fetch(`${BASE_URL}${url}`, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function fetchBanners() {
  return api("/ops/banners");
}

export function fetchChannels() {
  return api("/ops/channels");
}

export function fetchOrderList(token) {
  return fetch(`${BASE_URL}/pay/orders`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  }).then((r) => r.json());
}

export function fetchUserProfile(token) {
  return fetch(`${BASE_URL}/auth/profile`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  }).then((r) => r.json());
}
