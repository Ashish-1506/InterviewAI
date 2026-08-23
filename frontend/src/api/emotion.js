export const fastApiBaseUrl = (import.meta.env.VITE_FASTAPI_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export async function fastApiRequest(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
  };

  const token = localStorage.getItem('interviewai_token');
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`;

  if (!(typeof FormData !== 'undefined' && options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  const response = await fetch(`${fastApiBaseUrl}${path}`, {
    ...options,
    headers,
  });

  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : null;

  if (!response.ok) {
    throw new Error(data?.detail || data?.message || 'Request failed');
  }

  return data;
}

export function detectEmotionFrame(payload) {
  return fastApiRequest('/emotion/detect', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getEmotionReport(sessionId) {
  return fastApiRequest(`/emotion/report?session_id=${encodeURIComponent(sessionId)}`, {
    method: 'GET',
  });
}

