import { validate } from 'class-validator';
import { plainToInstance } from 'class-transformer';
import { CreateCoffeeDto } from './create-coffee.dto';

describe('CreateCoffeeDto', () => {
    const validDto = {
        name: 'Test Coffee',
        description: 'A delicious test coffee',
        type: 'Arabic',
        price: 15.99,
        imageUrl: 'https://example.com/coffee.jpg',
    };

    it('should pass validation with valid data', async () => {
        const dto = plainToInstance(CreateCoffeeDto, validDto);
        const errors = await validate(dto);
        expect(errors.length).toBe(0);
    });

    describe('name validation', () => {
        it('should fail when name is empty', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, name: '' });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'name')).toBe(true);
        });

        it('should fail when name exceeds 100 characters', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, name: 'a'.repeat(101) });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'name')).toBe(true);
        });
    });

    describe('type validation', () => {
        it('should pass with Arabic type', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, type: 'Arabic' });
            const errors = await validate(dto);
            expect(errors.length).toBe(0);
        });

        it('should pass with Robusta type', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, type: 'Robusta' });
            const errors = await validate(dto);
            expect(errors.length).toBe(0);
        });

        it('should fail with invalid type', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, type: 'InvalidType' });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'type')).toBe(true);
        });
    });

    describe('price validation', () => {
        it('should fail when price is negative', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, price: -5 });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'price')).toBe(true);
        });

        it('should fail when price exceeds 10000', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, price: 15000 });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'price')).toBe(true);
        });
    });

    describe('imageUrl validation', () => {
        it('should pass with valid https URL', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, imageUrl: 'https://example.com/img.jpg' });
            const errors = await validate(dto);
            expect(errors.length).toBe(0);
        });

        it('should pass with valid http URL', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, imageUrl: 'http://example.com/img.jpg' });
            const errors = await validate(dto);
            expect(errors.length).toBe(0);
        });

        it('should fail with javascript: URL (XSS prevention)', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, imageUrl: 'javascript:alert(1)' });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'imageUrl')).toBe(true);
        });

        it('should fail with data: URL', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, imageUrl: 'data:text/html,<script>alert(1)</script>' });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'imageUrl')).toBe(true);
        });

        it('should fail with URL without protocol', async () => {
            const dto = plainToInstance(CreateCoffeeDto, { ...validDto, imageUrl: 'example.com/img.jpg' });
            const errors = await validate(dto);
            expect(errors.some(e => e.property === 'imageUrl')).toBe(true);
        });
    });
});
