'use client';

import { useState } from 'react';
import styles from './Header.module.css';

interface HeaderProps {
    onCreateClick: () => void;
}

export default function Header({ onCreateClick }: HeaderProps) {
    return (
        <header className={styles.header}>
            <div className={styles.logo}>
                <span className={styles.logoAccent}>MVST</span>
                <span className={styles.logoText}> Coffee</span>
            </div>

            <button className={styles.createBtn} onClick={onCreateClick}>
                Create
            </button>
        </header>
    );
}
