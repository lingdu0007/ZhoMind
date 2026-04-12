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
    if (error?.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('username');
      localStorage.removeItem('role');
    }
    const message = error?.response?.data?.detail || error.message || '请求失败';
    return Promise.reject(new Error(message));
  }
);

export default http;
