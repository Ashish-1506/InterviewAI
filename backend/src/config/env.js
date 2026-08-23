require('dotenv').config();

const defaultFastApiParseUrl = process.env.NODE_ENV === 'production'
  ? 'http://fastapi:8000'
  : 'http://localhost:8000';

const config = {
  nodeEnv: process.env.NODE_ENV || 'development',
  port: Number(process.env.PORT || 4000),
  mongoUri: process.env.MONGODB_URI || 'mongodb://localhost:27017/interviewai',
  jwtSecret: process.env.JWT_SECRET || 'change-me',
  jwtExpiresIn: process.env.JWT_EXPIRES_IN || '7d',
  corsOrigin: process.env.CORS_ORIGIN || 'http://localhost:5173',
  bcryptSaltRounds: Number(process.env.BCRYPT_SALT_ROUNDS || 12),
  publicBaseUrl: process.env.PUBLIC_BASE_URL || 'http://localhost:4000',
  fastApiParseUrl: process.env.FASTAPI_PARSE_URL || defaultFastApiParseUrl,
  uploadsDir: process.env.UPLOADS_DIR || 'uploads',
};

module.exports = { config };
