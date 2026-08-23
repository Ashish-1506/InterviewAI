const { Schema, model } = require('mongoose');

const userSchema = new Schema({
  name: { type: String, required: true, trim: true },
  email: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    lowercase: true,
  },
  passwordHash: { type: String, required: true },
  resumeUrl: { type: String, default: '' },
  createdAt: { type: Date, default: Date.now, immutable: true },
});

module.exports = model('User', userSchema);
