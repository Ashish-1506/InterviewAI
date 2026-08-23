const jwt = require('jsonwebtoken');
const { config } = require('../config/env');

function authenticateToken(req, res, next) {
  const authorizationHeader = req.headers.authorization || '';
  const [scheme, token] = authorizationHeader.split(' ');

  if (scheme !== 'Bearer' || !token) {
    return res.status(401).json({ message: 'Missing or invalid token' });
  }

  try {
    req.user = jwt.verify(token, config.jwtSecret);
    return next();
  } catch (error) {
    return res.status(401).json({ message: 'Invalid or expired token' });
  }
}

module.exports = authenticateToken;
