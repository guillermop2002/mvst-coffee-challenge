import { Entity, PrimaryGeneratedColumn, Column } from 'typeorm';

@Entity('coffees')
export class Coffee {
  @PrimaryGeneratedColumn()
  id: number;

  @Column({ unique: true })
  name: string;

  @Column()
  description: string;

  @Column()
  type: string; // 'Arabic' or 'Robusta'

  @Column('decimal', { precision: 10, scale: 2 })
  price: number;

  @Column()
  imageUrl: string;
}
