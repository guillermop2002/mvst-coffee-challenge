// Coffee type definition
export interface Coffee {
    id: number;
    name: string;
    description: string;
    type: 'Arabic' | 'Robusta';
    price: number;
    imageUrl: string;
}

// For creating a new coffee (no id yet)
export interface CreateCoffee {
    name: string;
    description: string;
    type: string;
    price: number;
    imageUrl: string;
}
