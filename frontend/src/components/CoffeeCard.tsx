import styles from './CoffeeCard.module.css';

interface CoffeeCardProps {
    name: string;
    description: string;
    type: string;
    price: number;
    imageUrl: string;
}

export default function CoffeeCard({
    name,
    description,
    type,
    price,
    imageUrl
}: CoffeeCardProps) {
    return (
        <article className={styles.card}>
            <div className={styles.imageWrapper}>
                <span className={styles.tag}>{type}</span>
                <img
                    src={imageUrl}
                    alt={name}
                    className={styles.image}
                />
            </div>

            <div className={styles.content}>
                <h3 className={styles.name}>{name}</h3>
                <p className={styles.description}>{description}</p>
                <p className={styles.price}>{Number(price).toFixed(2)} €</p>
            </div>
        </article>
    );
}
