const fs = require('fs');
const path = require('path');
const multer = require('multer');
const User = require('../models/User');
const { config } = require('../config/env');

const allowedMimeTypes = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]);

function ensureUploadsDir() {
  const uploadsPath = path.resolve(process.cwd(), config.uploadsDir);
  if (!fs.existsSync(uploadsPath)) {
    fs.mkdirSync(uploadsPath, { recursive: true });
  }
  return uploadsPath;
}

const storage = multer.diskStorage({
  destination(req, file, callback) {
    callback(null, ensureUploadsDir());
  },
  filename(req, file, callback) {
    const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_');
    callback(null, `${Date.now()}-${safeName}`);
  },
});

const upload = multer({
  storage,
  fileFilter(req, file, callback) {
    if (!allowedMimeTypes.has(file.mimetype)) {
      return callback(new Error('Only PDF and DOCX files are supported'));
    }

    return callback(null, true);
  },
});

async function uploadResume(req, res, next) {
  upload.single('resume')(req, res, async (error) => {
    try {
      if (error) {
        return res.status(400).json({ message: error.message || 'Resume upload failed' });
      }

      if (!req.file) {
        return res.status(400).json({ message: 'No resume file received' });
      }

      const resumeUrl = `${config.publicBaseUrl}/uploads/${req.file.filename}`;
      const user = await User.findByIdAndUpdate(
        req.user.sub,
        { resumeUrl },
        { new: true },
      ).select('name email resumeUrl createdAt');

      if (!user) {
        return res.status(404).json({ message: 'User not found' });
      }

      return res.status(201).json({
        message: 'Resume uploaded successfully',
        resumeUrl,
        user,
      });
    } catch (controllerError) {
      return next(controllerError);
    }
  });
}

module.exports = {
  uploadResume,
};
