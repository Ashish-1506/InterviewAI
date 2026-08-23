const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const User = require('../models/User');
const { config } = require('../config/env');

function createToken(user) {
  return jwt.sign(
    {
      sub: user._id.toString(),
      email: user.email,
      name: user.name,
    },
    config.jwtSecret,
    { expiresIn: config.jwtExpiresIn },
  );
}

function sanitizeUser(user) {
  return {
    id: user._id,
    name: user.name,
    email: user.email,
    resumeUrl: user.resumeUrl,
    createdAt: user.createdAt,
  };
}

async function signup(req, res, next) {
  try {
    const { name, email, password, resumeUrl } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ message: 'name, email, and password are required' });
    }

    const existingUser = await User.findOne({ email: email.toLowerCase() });
    if (existingUser) {
      return res.status(409).json({ message: 'Email already registered' });
    }

    const passwordHash = await bcrypt.hash(password, config.bcryptSaltRounds);
    const user = await User.create({
      name,
      email: email.toLowerCase(),
      passwordHash,
      resumeUrl: resumeUrl || '',
    });

    return res.status(201).json({
      token: createToken(user),
      user: sanitizeUser(user),
    });
  } catch (error) {
    return next(error);
  }
}

async function login(req, res, next) {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ message: 'email and password are required' });
    }

    const user = await User.findOne({ email: email.toLowerCase() });
    if (!user) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }

    const passwordMatches = await bcrypt.compare(password, user.passwordHash);
    if (!passwordMatches) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }

    return res.json({
      token: createToken(user),
      user: sanitizeUser(user),
    });
  } catch (error) {
    return next(error);
  }
}

module.exports = {
  signup,
  login,
};
