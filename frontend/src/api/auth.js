import { apiRequest, clearAuthToken, setAuthToken } from './client';

async function requestAuth(path, payload) {
  return apiRequest(`/auth/${path}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function signup(payload) {
  return requestAuth('signup', payload);
}

export function login(payload) {
  return requestAuth('login', payload);
}

export function persistAuthSession({ token, user }) {
  if (token) {
    setAuthToken(token);
  }

  if (user) {
    localStorage.setItem('interviewai_user', JSON.stringify(user));
  }
}

export function clearAuthSession() {
  clearAuthToken();
  localStorage.removeItem('interviewai_user');
}

