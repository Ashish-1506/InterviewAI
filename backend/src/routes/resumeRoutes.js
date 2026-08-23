const { Router } = require('express');
const { uploadResume } = require('../controllers/resumeController');
const authenticateToken = require('../middleware/authMiddleware');

const router = Router();

router.post('/upload', authenticateToken, uploadResume);

module.exports = router;
