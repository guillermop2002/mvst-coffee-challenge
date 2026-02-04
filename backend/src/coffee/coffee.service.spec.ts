import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { ConflictException } from '@nestjs/common';
import { CoffeeService } from './coffee.service';
import { Coffee } from './coffee.entity';

// Mock repository
const mockCoffeeRepository = {
    find: jest.fn(),
    findOne: jest.fn(),
    create: jest.fn(),
    save: jest.fn(),
};

describe('CoffeeService', () => {
    let service: CoffeeService;

    beforeEach(async () => {
        const module: TestingModule = await Test.createTestingModule({
            providers: [
                CoffeeService,
                {
                    provide: getRepositoryToken(Coffee),
                    useValue: mockCoffeeRepository,
                },
            ],
        }).compile();

        service = module.get<CoffeeService>(CoffeeService);

        // Clear mocks between tests
        jest.clearAllMocks();
    });

    it('should be defined', () => {
        expect(service).toBeDefined();
    });

    describe('findAll', () => {
        const mockCoffees = [
            { id: 1, name: 'Espresso', type: 'Arabic', price: 15, description: 'Strong', imageUrl: 'http://example.com/1.jpg' },
            { id: 2, name: 'Latte', type: 'Robusta', price: 18, description: 'Smooth', imageUrl: 'http://example.com/2.jpg' },
        ];

        it('should return all coffees when no filter is provided', async () => {
            mockCoffeeRepository.find.mockResolvedValue(mockCoffees);

            const result = await service.findAll();

            expect(result).toEqual(mockCoffees);
            expect(mockCoffeeRepository.find).toHaveBeenCalledWith();
        });

        it('should filter coffees by type when type is provided', async () => {
            const arabicCoffees = [mockCoffees[0]];
            mockCoffeeRepository.find.mockResolvedValue(arabicCoffees);

            const result = await service.findAll('Arabic');

            expect(result).toEqual(arabicCoffees);
            expect(mockCoffeeRepository.find).toHaveBeenCalledWith({ where: { type: 'Arabic' } });
        });
    });

    describe('create', () => {
        const createDto = {
            name: 'New Coffee',
            description: 'Fresh brew',
            type: 'Arabic',
            price: 20,
            imageUrl: 'http://example.com/new.jpg',
        };

        it('should create a new coffee when name is unique', async () => {
            const savedCoffee = { id: 1, ...createDto };
            mockCoffeeRepository.findOne.mockResolvedValue(null); // No existing coffee
            mockCoffeeRepository.create.mockReturnValue(createDto);
            mockCoffeeRepository.save.mockResolvedValue(savedCoffee);

            const result = await service.create(createDto);

            expect(result).toEqual(savedCoffee);
            expect(mockCoffeeRepository.findOne).toHaveBeenCalledWith({ where: { name: createDto.name } });
            expect(mockCoffeeRepository.create).toHaveBeenCalledWith(createDto);
            expect(mockCoffeeRepository.save).toHaveBeenCalled();
        });

        it('should throw ConflictException when coffee name already exists', async () => {
            const existingCoffee = { id: 1, name: 'New Coffee' };
            mockCoffeeRepository.findOne.mockResolvedValue(existingCoffee);

            await expect(service.create(createDto)).rejects.toThrow(ConflictException);
            await expect(service.create(createDto)).rejects.toThrow('A coffee with the same name already exists');

            // Verify save was never called
            expect(mockCoffeeRepository.save).not.toHaveBeenCalled();
        });
    });
});
