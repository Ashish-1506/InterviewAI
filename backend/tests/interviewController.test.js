const assert = require('assert');
const { parseResumeWithFastApi } = require('../src/controllers/interviewController');

(async () => {
  const originalFetch = global.fetch;
  global.fetch = async () => {
    throw new Error('fetch failed');
  };

  try {
    const payload = await parseResumeWithFastApi('http://example.com/resume.pdf', {});
    assert.deepStrictEqual(payload, {
      skills: [],
      projects: [],
      experience: [],
      education: [],
    });
    console.log('interviewController fallback test passed');
  } finally {
    global.fetch = originalFetch;
  }
})();
