import { DataSource } from 'typeorm';
import { Coffee } from './coffee/coffee.entity';

const dataSource = new DataSource({
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
});

const coffees = [
    {
        name: 'Dark Roast',
        description: 'Free in the MVST office',
        type: 'Robusta',
        price: 19.00,
        imageUrl: 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=400',
    },
    {
        name: 'Americano',
        description: 'Free in the MVST office',
        type: 'Arabic',
        price: 20.00,
        imageUrl: 'https://images.unsplash.com/photo-1521302080334-4bebac2763a6?w=400',
    },
    {
        name: 'Cappuccino',
        description: 'Free in the MVST office',
        type: 'Arabic',
        price: 15.00,
        imageUrl: 'https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=400',
    },
    {
        name: 'Decaf Americano',
        description: 'Free in the MVST office',
        type: 'Robusta',
        price: 20.00,
        imageUrl: 'https://images.unsplash.com/photo-1485808191679-5f86510681a2?w=400',
    },
    {
        name: 'Pine Roast',
        description: 'Free in the MVST office',
        type: 'Arabic',
        price: 18.00,
        imageUrl: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=400',
    },
    {
        name: 'Raphael Original',
        description: 'Free in the MVST office',
        type: 'Arabic',
        price: 16.00,
        imageUrl: 'https://images.unsplash.com/photo-1497935586351-b67a49e012bf?w=400',
    },
];

async function seed() {
    await dataSource.initialize();
    console.log('Database connected');

    const coffeeRepo = dataSource.getRepository(Coffee);

    // Clear existing data
    await coffeeRepo.clear();
    console.log('Cleared existing coffees');

    // Insert seed data
    for (const coffee of coffees) {
        await coffeeRepo.save(coffee);
        console.log(`Created: ${coffee.name}`);
    }

    console.log('Seeding complete!');
    await dataSource.destroy();
}

seed().catch(console.error);
