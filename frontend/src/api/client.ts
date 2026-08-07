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
      // These are public routes rendered under GroupProvider, which always
      // calls GET /users/me. For a logged-out visitor that 401s, so every
      // public route must be exempted here or it bounces straight to
      // /login before it can render. Add new public routes to this list.
      if (
        path !== "/login" &&
        path !== "/register" &&
        !path.startsWith("/invite") &&
        !path.startsWith("/reset-password")
      ) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default client;
