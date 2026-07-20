import { useEffect, useState } from 'react';
import styles from './SplashScreen.module.css';

interface SplashScreenProps {
  onDone: () => void;
}

export default function SplashScreen({ onDone }: SplashScreenProps) {
  const [phase, setPhase] = useState<'enter' | 'hold' | 'exit'>('enter');

  useEffect(() => {
    // enter → hold → exit
    const t1 = setTimeout(() => setPhase('hold'), 300);
    const t2 = setTimeout(() => setPhase('exit'), 900);
    const t3 = setTimeout(() => onDone(), 1300);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [onDone]);

  return (
    <div className={`${styles.splash} ${phase === 'exit' ? styles.exit : ''}`}>
      {/* Radial glow behind logo */}
      <div className={`${styles.glow} ${phase !== 'enter' ? styles.glowVisible : ''}`} />

      {/* Orbiting ring */}
      <div className={`${styles.ring} ${phase !== 'enter' ? styles.ringVisible : ''}`} />
      <div className={`${styles.ring2} ${phase !== 'enter' ? styles.ringVisible : ''}`} />

      {/* Logo */}
      <div className={`${styles.logoWrap} ${phase !== 'enter' ? styles.logoVisible : ''}`}>
        <img src="/logo.png" alt="Tiflo AI" className={styles.logo} />
      </div>

      {/* Brand name */}
      <div className={`${styles.brand} ${phase === 'hold' ? styles.brandVisible : ''}`}>
        <span className={styles.brandName}>Tiflo AI</span>
        <span className={styles.brandTagline}>Premium Intelligence Engine</span>
      </div>

      {/* Loading dots */}
      <div className={`${styles.dots} ${phase === 'hold' ? styles.dotsVisible : ''}`}>
        <span /><span /><span />
      </div>
    </div>
  );
}
