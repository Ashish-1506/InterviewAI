const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const path = require('path');
const { config } = require('./config/env');
const authRoutes = require('./routes/authRoutes');
const resumeRoutes = require('./routes/resumeRoutes');
const interviewRoutes = require('./routes/interviewRoutes');
const userRoutes = require('./routes/userRoutes');

const app = express();

app.use(cors({ origin: config.corsOrigin }));
app.use(express.json());
app.use(morgan('dev'));

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.use('/uploads', express.static(path.join(process.cwd(), 'uploads')));
app.use('/api/auth', authRoutes);
app.use('/api/resume', resumeRoutes);
app.use('/api/interviews', interviewRoutes);
app.use('/api/users', userRoutes);

app.use((req, res) => {
  res.status(404).json({ message: 'Route not found' });
});

module.exports = app;
