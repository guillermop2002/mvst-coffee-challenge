'use client';

import { useEffect } from 'react';
import styles from './Toast.module.css';

interface ToastProps {
    message: string;
    isVisible: boolean;
    onClose: () => void;
}

export default function Toast({ message, isVisible, onClose }: ToastProps) {
    // Auto-hide after 5 seconds
    useEffect(() => {
        if (isVisible) {
            const timer = setTimeout(onClose, 5000);
            return () => clearTimeout(timer);
        }
    }, [isVisible, onClose]);

    if (!isVisible) return null;

    return (
        <div className={styles.toast}>
            <div className={styles.content}>
                <span className={styles.icon}>⚠️</span>
                <p className={styles.message}>{message}</p>
            </div>
            <button className={styles.closeBtn} onClick={onClose}>
                ×
            </button>
        </div>
    );
}
