const { Schema, model, Types } = require('mongoose');

const interviewSessionSchema = new Schema({
  userId: { type: Types.ObjectId, ref: 'User', required: true, index: true },
  targetRole: { type: String, required: true, trim: true },
  type: {
    type: String,
    required: true,
    enum: ['HR', 'Technical'],
  },
  status: {
    type: String,
    required: true,
    enum: ['pending', 'active', 'completed', 'cancelled'],
    default: 'pending',
  },
  startedAt: { type: Date, default: null },
  endedAt: { type: Date, default: null },
  parsedResumeJson: { type: Schema.Types.Mixed, default: null },
  conversationTurns: {
    type: [
      {
        question: { type: String, default: '' },
        answer: { type: String, default: '' },
        timestamp: { type: Date, default: Date.now },
        mode: { type: String, enum: ['HR', 'Technical'], default: 'HR' },
        questionId: { type: String, default: null },
      },
    ],
    default: [],
  },
});


module.exports = model('InterviewSession', interviewSessionSchema);
