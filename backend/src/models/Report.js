const { Schema, model, Types } = require('mongoose');

const reportSchema = new Schema({
  sessionId: {
    type: Types.ObjectId,
    ref: 'InterviewSession',
    required: true,
    unique: true,
  },
  score: { type: Number, required: true, min: 0, max: 100 },
  weaknesses: { type: [String], default: [] },
  createdAt: { type: Date, default: Date.now, immutable: true },
});

module.exports = model('Report', reportSchema);
