const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000/api';
const authTokenKey = 'interviewai_token';

export function getAuthToken() {
  return localStorage.getItem(authTokenKey);
}

export function setAuthToken(token) {
  localStorage.setItem(authTokenKey, token);
}

export function clearAuthToken() {
  localStorage.removeItem(authTokenKey);
}

async function parseJsonResponse(response) {
  const contentType = response.headers.get('content-type') || '';

  if (!contentType.includes('application/json')) {
    return null;
  }

  return response.json();
}

export async function apiRequest(path, options = {}) {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers = {
    ...(options.headers || {}),
  };

  if (!isFormData) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  const token = getAuthToken();
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  const data = await parseJsonResponse(response);

  if (!response.ok) {
    const error = new Error(data?.message || 'Request failed');
    error.status = response.status;
    throw error;
  }

  return data;
}

export function apiBaseUrlForUploads() {
  return apiBaseUrl.replace(/\/api$/, '');
}
