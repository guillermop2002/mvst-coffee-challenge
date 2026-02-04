import CoffeeCard from './CoffeeCard';
import styles from './CoffeeGrid.module.css';

interface Coffee {
    id: number;
    name: string;
    description: string;
    type: string;
    price: number;
    imageUrl: string;
}

interface CoffeeGridProps {
    coffees: Coffee[];
}

export default function CoffeeGrid({ coffees }: CoffeeGridProps) {
    if (coffees.length === 0) {
        return (
            <div className={styles.empty}>
                <p>No coffees found. Try adding one!</p>
            </div>
        );
    }

    return (
        <div className={styles.grid}>
            {coffees.map((coffee) => (
                <CoffeeCard
                    key={coffee.id}
                    name={coffee.name}
                    description={coffee.description}
                    type={coffee.type}
                    price={coffee.price}
                    imageUrl={coffee.imageUrl}
                />
            ))}
        </div>
    );
}
