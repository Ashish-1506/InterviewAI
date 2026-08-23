const { Router } = require('express');
const authenticateToken = require('../middleware/authMiddleware');
const User = require('../models/User');

const router = Router();

router.get('/me', authenticateToken, async (req, res, next) => {
  try {
    const user = await User.findById(req.user.sub).select('name email resumeUrl createdAt');

    if (!user) {
      return res.status(404).json({ message: 'User not found' });
    }

    return res.json({ user });
  } catch (error) {
    return next(error);
  }
});

module.exports = router;
