const User = require('../models/User');
const InterviewSession = require('../models/InterviewSession');
const { config } = require('../config/env');

async function parseResumeWithFastApi(resumeUrl, req) {
  const fallbackPayload = {
    skills: [],
    projects: [],
    experience: [],
    education: [],
  };

  try {
    const response = await fetch(`${config.fastApiParseUrl}/parse-resume`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(req?.headers?.authorization ? { Authorization: req.headers.authorization } : {}),
      },
      body: JSON.stringify({ file_url: resumeUrl }),
    });

    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(payload?.detail || payload?.message || 'Resume parsing failed');
    }

    if (payload && typeof payload === 'object') {
      return payload;
    }

    throw new Error('Resume parser returned an invalid payload');
  } catch (error) {
    console.warn('Resume parsing unavailable; continuing with empty parsed resume data.', error.message || error);
    return fallbackPayload;
  }
}

async function startInterviewSession(req, res, next) {
  try {
    const { type, targetRole } = req.body;

    if (!type || !targetRole) {
      return res.status(400).json({ message: 'type and targetRole are required' });
    }

    if (!['HR', 'Technical'].includes(type)) {
      return res.status(400).json({ message: 'type must be HR or Technical' });
    }

    const user = await User.findById(req.user.sub);
    if (!user) {
      return res.status(404).json({ message: 'User not found' });
    }

    if (!user.resumeUrl) {
      return res.status(400).json({ message: 'Upload a resume before starting an interview' });
    }

    const parsedResumeJson = await parseResumeWithFastApi(user.resumeUrl, req);

    const interviewSession = await InterviewSession.create({
      userId: user._id,
      targetRole,
      type,
      status: 'active',
      startedAt: new Date(),
      parsedResumeJson,
      conversationTurns: [],
    });


    return res.status(201).json({
      sessionId: interviewSession._id,
      interviewSession,
    });
  } catch (error) {
    return res.status(400).json({
      message: error.message || 'Could not start interview session',
    });
  }
}

module.exports = {
  parseResumeWithFastApi,
  startInterviewSession,
};
