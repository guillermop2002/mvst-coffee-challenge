import styles from './Footer.module.css';

export default function Footer() {
    return (
        <footer className={styles.footer}>
            <div className={styles.logo}>
                <span className={styles.logoAccent}>MVST</span>
                <span className={styles.logoText}> Coffee</span>
            </div>
            <p className={styles.credits}>© 2026 MVST. All rights reserved.</p>
        </footer>
    );
}
