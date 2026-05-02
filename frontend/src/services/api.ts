import axios from 'axios';

import type { ApiError } from '../types/api';
import { API_TIMEOUT_MS } from '../utils/constants';

const baseURL = import.meta.env.VITE_API_BASE_URL || '';

export const apiClient = axios.create({
  baseURL,
  timeout: API_TIMEOUT_MS,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API request failed', error);
    const apiError: ApiError = {
      message:
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        '请求失败',
      detail: error.response?.data,
      status: error.response?.status ?? 500,
    };
    return Promise.reject(apiError);
  },
);
