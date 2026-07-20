
import styles from './PageContainer.module.css';

interface PageContainerProps {
  title: string;
  children: React.ReactNode;
}

export default function PageContainer({ title, children }: PageContainerProps) {
  return (
    <div className={styles.container}>
      <div className={styles.content}>
        <h1>{title}</h1>
        <div className={styles.glassCard}>
          {children}
        </div>
      </div>
    </div>
  );
}
