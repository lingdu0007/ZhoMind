import axios from 'axios';

const fallbackBaseURL = `${window.location.protocol}//${window.location.hostname}:8000`;
const baseURL = import.meta.env.VITE_API_BASE_URL || fallbackBaseURL;

const http = axios.create({
  baseURL,
  timeout: 30000
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const payload = error?.response?.data || {};
    if (status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('username');
      localStorage.removeItem('role');
    }

    const normalizedError = new Error(payload.message || payload.detail || error.message || '请求失败');
    normalizedError.status = status || 0;
    normalizedError.code = payload.code || '';
    normalizedError.detail = payload.detail;
    normalizedError.request_id = payload.request_id || '';
    return Promise.reject(normalizedError);
  }
);

export default http;
