import axios from "axios";

const client = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  // Serialize array params as repeated keys (?pictograms=GHS05&pictograms=GHS02)
  // to match FastAPI's list[str] query parsing, instead of the default `key[]=`.
  paramsSerializer: { indexes: null },
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const path = window.location.pathname;
      if (path !== "/login" && path !== "/register" && !path.startsWith("/invite")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default client;
