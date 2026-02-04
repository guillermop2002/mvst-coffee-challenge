import styles from './Hero.module.css';

interface HeroProps {
    onCreateClick: () => void;
}

export default function Hero({ onCreateClick }: HeroProps) {
    return (
        <section className={styles.hero}>
            <div className={styles.content}>
                <h1 className={styles.title}>ROASTED COFFEE</h1>
                <p className={styles.subtitle}>
                    Choose a coffee from below or create your own.
                </p>
                <button className={styles.ctaBtn} onClick={onCreateClick}>
                    Create your own coffee
                </button>
            </div>

            <div className={styles.imageWrapper}>
                {/* Coffee cup image - using a placeholder that matches Figma */}
                <img
                    src="https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=600"
                    alt="Delicious coffee cup"
                    className={styles.coffeeImage}
                />
            </div>
        </section>
    );
}
