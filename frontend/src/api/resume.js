import { apiRequest } from './client';

export async function uploadResume(file) {
  const formData = new FormData();
  formData.append('resume', file);

  return apiRequest('/resume/upload', {
    method: 'POST',
    body: formData,
  });
}
