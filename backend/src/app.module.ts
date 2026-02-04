import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { APP_GUARD } from '@nestjs/core';
import { CoffeeModule } from './coffee/coffee.module';
import { Coffee } from './coffee/coffee.entity';

@Module({
  imports: [
    // Rate limiting: 10 requests per 60 seconds per IP
    ThrottlerModule.forRoot([{
      ttl: 60000,
      limit: 10,
    }]),
    TypeOrmModule.forRoot({
      type: 'postgres',
      url: process.env.DATABASE_URL,
      host: process.env.DATABASE_URL ? undefined : 'localhost',
      port: process.env.DATABASE_URL ? undefined : 5432,
      username: process.env.DATABASE_URL ? undefined : 'postgres',
      password: process.env.DATABASE_URL ? undefined : '1234',
      database: process.env.DATABASE_URL ? undefined : 'mvst-coffee-challenge-db',
      entities: [Coffee],
      synchronize: true,
      ssl: process.env.DATABASE_URL ? { rejectUnauthorized: false } : false,
    }),
    CoffeeModule,
  ],
  controllers: [],
  providers: [
    // Apply rate limiting globally
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
  ],
})
export class AppModule { }


