import { Controller, Get, Post, Body, Query } from '@nestjs/common';
import { CoffeeService } from './coffee.service';
import { CreateCoffeeDto } from './dto/create-coffee.dto';
import { Coffee } from './coffee.entity';

@Controller('coffees')
export class CoffeeController {
    constructor(private readonly coffeeService: CoffeeService) { }

    @Get()
    findAll(@Query('type') type?: string): Promise<Coffee[]> {
        return this.coffeeService.findAll(type);
    }

    @Post()
    create(@Body() createCoffeeDto: CreateCoffeeDto): Promise<Coffee> {
        return this.coffeeService.create(createCoffeeDto);
    }
}
