import { Coffee, CreateCoffee } from '@/types/Coffee';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000';

// Get all coffees, optionally filtered by type
export async function getCoffees(type?: string): Promise<Coffee[]> {
    const url = type && type !== 'All'
        ? `${API_URL}/coffees?type=${type}`
        : `${API_URL}/coffees`;

    const response = await fetch(url, {
        cache: 'no-store', // Always fetch fresh data
    });

    if (!response.ok) {
        throw new Error('Failed to fetch coffees');
    }

    return response.json();
}

// Create a new coffee
export async function createCoffee(coffee: CreateCoffee): Promise<Coffee> {
    const response = await fetch(`${API_URL}/coffees`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(coffee),
    });

    if (response.status === 409) {
        throw new Error('A coffee with the same name already exists');
    }

    if (!response.ok) {
        throw new Error('Failed to create coffee');
    }

    return response.json();
}
