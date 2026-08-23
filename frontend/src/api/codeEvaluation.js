import { fastApiRequest } from './emotion';

export async function evaluateCode(payload) {
  return fastApiRequest('/evaluate-code', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

