import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import helmet from 'helmet';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  // Security headers (XSS protection, content-type sniffing, etc.)
  app.use(helmet());

  // CORS for frontend communication
  app.enableCors({
    origin: process.env.FRONTEND_URL || 'http://localhost:3000',
    methods: ['GET', 'POST'],
  });

  // DTO validation with whitelist to strip unknown properties
  app.useGlobalPipes(new ValidationPipe({
    whitelist: true,
    transform: true,
    transformOptions: {
      enableImplicitConversion: true,
    },
  }));

  const port = process.env.PORT || 5000;
  await app.listen(port);
  console.log(`Backend running on port ${port}`);
}
bootstrap();


