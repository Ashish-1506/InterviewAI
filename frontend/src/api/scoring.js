import { fastApiRequest } from './emotion';

export function getFinalScoringReport(sessionId) {
  return fastApiRequest(`/api/scoring/report?session_id=${encodeURIComponent(sessionId)}`, {
    method: 'GET',
  });
}

