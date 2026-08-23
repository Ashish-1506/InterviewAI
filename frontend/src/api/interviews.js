import { apiRequest } from './client';

export function startInterviewSession(payload) {
  return apiRequest('/interviews/start', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
