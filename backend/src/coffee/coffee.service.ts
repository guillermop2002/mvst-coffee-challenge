import { Injectable, ConflictException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Coffee } from './coffee.entity';
import { CreateCoffeeDto } from './dto/create-coffee.dto';

@Injectable()
export class CoffeeService {
    constructor(
        @InjectRepository(Coffee)
        private coffeeRepository: Repository<Coffee>,
    ) { }

    async findAll(type?: string): Promise<Coffee[]> {
        if (type) {
            return this.coffeeRepository.find({ where: { type } });
        }
        return this.coffeeRepository.find();
    }

    async create(createCoffeeDto: CreateCoffeeDto): Promise<Coffee> {
        // Prevent duplicate coffee names
        const existing = await this.coffeeRepository.findOne({
            where: { name: createCoffeeDto.name },
        });

        if (existing) {
            throw new ConflictException('A coffee with the same name already exists');
        }

        const coffee = this.coffeeRepository.create(createCoffeeDto);
        return this.coffeeRepository.save(coffee);
    }
}
