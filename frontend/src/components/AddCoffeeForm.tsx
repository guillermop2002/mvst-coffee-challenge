'use client';

import { useState } from 'react';
import styles from './AddCoffeeForm.module.css';

interface AddCoffeeFormProps {
    onSubmit: (coffee: {
        name: string;
        description: string;
        type: string;
        price: number;
        imageUrl: string;
    }) => void;
    onCancel: () => void;
    isSubmitting: boolean;
}

export default function AddCoffeeForm({ onSubmit, onCancel, isSubmitting }: AddCoffeeFormProps) {
    const [name, setName] = useState('');
    const [price, setPrice] = useState('');
    const [type, setType] = useState<'Arabic' | 'Robusta'>('Arabic');
    const [imageUrl, setImageUrl] = useState('');
    const [description, setDescription] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        if (!name || !price || !imageUrl || !description) {
            return; // Basic validation
        }

        onSubmit({
            name,
            description,
            type,
            price: parseFloat(price),
            imageUrl,
        });
    };

    return (
        <form onSubmit={handleSubmit} className={styles.form}>
            <h2 className={styles.title}>CREATE NEW</h2>

            <div className={styles.row}>
                <div className={styles.field}>
                    <label className={styles.label}>Name</label>
                    <input
                        type="text"
                        className={styles.input}
                        placeholder="Name your coffee here"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </div>

                <div className={styles.fieldSmall}>
                    <label className={styles.label}>Price</label>
                    <div className={styles.priceWrapper}>
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            className={styles.input}
                            placeholder="0.00"
                            value={price}
                            onChange={(e) => setPrice(e.target.value)}
                            required
                        />
                        <span className={styles.currency}>€</span>
                    </div>
                </div>
            </div>

            <div className={styles.field}>
                <label className={styles.label}>Type</label>
                <div className={styles.typeToggle}>
                    <button
                        type="button"
                        className={`${styles.typeBtn} ${type === 'Arabic' ? styles.active : ''}`}
                        onClick={() => setType('Arabic')}
                    >
                        Arabic
                    </button>
                    <button
                        type="button"
                        className={`${styles.typeBtn} ${type === 'Robusta' ? styles.active : ''}`}
                        onClick={() => setType('Robusta')}
                    >
                        Robusta
                    </button>
                </div>
            </div>

            <div className={styles.field}>
                <label className={styles.label}>Upload image</label>
                <input
                    type="url"
                    className={styles.input}
                    placeholder="Paste image URL here"
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    required
                />
            </div>

            <div className={styles.field}>
                <label className={styles.label}>Description</label>
                <textarea
                    className={styles.textarea}
                    placeholder="Add a description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={3}
                    required
                />
            </div>

            <div className={styles.actions}>
                <button
                    type="button"
                    className={styles.discardBtn}
                    onClick={onCancel}
                    disabled={isSubmitting}
                >
                    Discard
                </button>
                <button
                    type="submit"
                    className={styles.confirmBtn}
                    disabled={isSubmitting}
                >
                    {isSubmitting ? 'Saving...' : 'Confirm'}
                </button>
            </div>
        </form>
    );
}
