const mongoose = require('mongoose');
const { config } = require('./env');

async function connectDatabase() {
  mongoose.set('strictQuery', true);
  await mongoose.connect(config.mongoUri);
  console.log('Connected to MongoDB');
}

module.exports = connectDatabase;
