const { Router } = require('express');
const authenticateToken = require('../middleware/authMiddleware');
const { startInterviewSession } = require('../controllers/interviewController');

const router = Router();

router.post('/start', authenticateToken, startInterviewSession);

module.exports = router;
