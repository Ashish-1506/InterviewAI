const app = require('./app');
const connectDatabase = require('./config/db');
const { config } = require('./config/env');

async function bootstrap() {
  await connectDatabase();

  app.listen(config.port, () => {
    console.log(`Node API listening on ${config.port}`);
  });
}

bootstrap().catch((error) => {
  console.error('Failed to start Node API', error);
  process.exit(1);
});
