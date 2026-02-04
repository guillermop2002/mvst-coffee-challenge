'use client';

import { useState, useEffect, useCallback } from 'react';
import Header from '@/components/Header';
import Hero from '@/components/Hero';
import FilterTabs from '@/components/FilterTabs';
import CoffeeGrid from '@/components/CoffeeGrid';
import Modal from '@/components/Modal';
import AddCoffeeForm from '@/components/AddCoffeeForm';
import Toast from '@/components/Toast';
import Footer from '@/components/Footer';
import { Coffee, CreateCoffee } from '@/types/Coffee';
import { getCoffees, createCoffee } from '@/services/api';
import styles from './page.module.css';

type FilterType = 'All' | 'Arabic' | 'Robusta';

export default function Home() {
  const [coffees, setCoffees] = useState<Coffee[]>([]);
  const [filter, setFilter] = useState<FilterType>('All');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState({ message: '', isVisible: false });

  // Fetches coffees whenever filter changes
  const fetchCoffees = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await getCoffees(filter);
      setCoffees(data);
    } catch (error) {
      console.error('Failed to fetch coffees:', error);
    } finally {
      setIsLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchCoffees();
  }, [fetchCoffees]);

  const handleCreateCoffee = async (coffeeData: CreateCoffee) => {
    try {
      setIsSubmitting(true);
      await createCoffee(coffeeData);
      setIsModalOpen(false);
      fetchCoffees(); // Refresh the list
    } catch (error: any) {
      setToast({
        message: error.message || 'Failed to create coffee',
        isVisible: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const openModal = () => setIsModalOpen(true);
  const closeModal = () => setIsModalOpen(false);
  const closeToast = () => setToast({ ...toast, isVisible: false });

  return (
    <main className={styles.main}>
      <Header onCreateClick={openModal} />
      <Hero onCreateClick={openModal} />

      <section className={styles.coffeeSection}>
        <h2 className={styles.sectionTitle}>MVST. EXCLUSIVE COFFEE</h2>
        <FilterTabs activeFilter={filter} onFilterChange={setFilter} />

        {isLoading ? (
          <div className={styles.loading}>Loading coffees...</div>
        ) : (
          <CoffeeGrid coffees={coffees} />
        )}
      </section>

      <Footer />

      <Modal isOpen={isModalOpen} onClose={closeModal}>
        <AddCoffeeForm
          onSubmit={handleCreateCoffee}
          onCancel={closeModal}
          isSubmitting={isSubmitting}
        />
      </Modal>

      <Toast
        message={toast.message}
        isVisible={toast.isVisible}
        onClose={closeToast}
      />
    </main>
  );
}
