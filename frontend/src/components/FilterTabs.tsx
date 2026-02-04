'use client';

import styles from './FilterTabs.module.css';

type FilterType = 'All' | 'Arabic' | 'Robusta';

interface FilterTabsProps {
    activeFilter: FilterType;
    onFilterChange: (filter: FilterType) => void;
}

export default function FilterTabs({ activeFilter, onFilterChange }: FilterTabsProps) {
    const filters: FilterType[] = ['All', 'Arabic', 'Robusta'];

    return (
        <div className={styles.tabs}>
            {filters.map((filter) => (
                <button
                    key={filter}
                    className={`${styles.tab} ${activeFilter === filter ? styles.active : ''}`}
                    onClick={() => onFilterChange(filter)}
                >
                    {filter}
                </button>
            ))}
        </div>
    );
}
