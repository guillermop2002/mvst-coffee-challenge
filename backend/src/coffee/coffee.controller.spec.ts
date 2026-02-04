import { Test, TestingModule } from '@nestjs/testing';
import { CoffeeController } from './coffee.controller';
import { CoffeeService } from './coffee.service';

// Mock service
const mockCoffeeService = {
    findAll: jest.fn(),
    create: jest.fn(),
};

describe('CoffeeController', () => {
    let controller: CoffeeController;

    beforeEach(async () => {
        const module: TestingModule = await Test.createTestingModule({
            controllers: [CoffeeController],
            providers: [
                {
                    provide: CoffeeService,
                    useValue: mockCoffeeService,
                },
            ],
        }).compile();

        controller = module.get<CoffeeController>(CoffeeController);

        jest.clearAllMocks();
    });

    it('should be defined', () => {
        expect(controller).toBeDefined();
    });

    describe('findAll', () => {
        const mockCoffees = [
            { id: 1, name: 'Espresso', type: 'Arabic', price: 15, description: 'Strong', imageUrl: 'http://example.com/1.jpg' },
            { id: 2, name: 'Latte', type: 'Robusta', price: 18, description: 'Smooth', imageUrl: 'http://example.com/2.jpg' },
        ];

        it('should return all coffees', async () => {
            mockCoffeeService.findAll.mockResolvedValue(mockCoffees);

            const result = await controller.findAll();

            expect(result).toEqual(mockCoffees);
            expect(mockCoffeeService.findAll).toHaveBeenCalledWith(undefined);
        });

        it('should pass type filter to service', async () => {
            const arabicCoffees = [mockCoffees[0]];
            mockCoffeeService.findAll.mockResolvedValue(arabicCoffees);

            const result = await controller.findAll('Arabic');

            expect(result).toEqual(arabicCoffees);
            expect(mockCoffeeService.findAll).toHaveBeenCalledWith('Arabic');
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

        it('should create and return a new coffee', async () => {
            const createdCoffee = { id: 1, ...createDto };
            mockCoffeeService.create.mockResolvedValue(createdCoffee);

            const result = await controller.create(createDto);

            expect(result).toEqual(createdCoffee);
            expect(mockCoffeeService.create).toHaveBeenCalledWith(createDto);
        });
    });
});
