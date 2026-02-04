import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { Coffee } from './coffee.entity';
import { CoffeeService } from './coffee.service';
import { CoffeeController } from './coffee.controller';

@Module({
    imports: [TypeOrmModule.forFeature([Coffee])],
    controllers: [CoffeeController],
    providers: [CoffeeService],
    exports: [CoffeeService],
})
export class CoffeeModule { }
