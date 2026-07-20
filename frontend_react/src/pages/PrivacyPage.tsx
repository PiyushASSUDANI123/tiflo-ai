import PageContainer from '../components/PageContainer';
import { Eye, Keyboard, Database, Lock } from 'lucide-react';
import styles from './InfoPages.module.css';

export default function PrivacyPage() {
  return (
    <PageContainer title="Privacy Policies">
      <div className={styles.content}>
        <p className={styles.lead}>
          Transparency is our core principle. Tiflo AI is built on the philosophy that <strong>"We take everything, so you don't have to worry about anything."</strong> Here is exactly what we collect and why.
        </p>

        <div className={styles.sectionBox}>
          <h3><Eye size={20} className={styles.icon} /> Telemetry & Digital Identity</h3>
          <p>We log your IP address, browser fingerprint, device metadata, and session durations. This allows our backend nodes to pre-warm the specific AI models tailored to your hardware and connection speed.</p>
        </div>

        <div className={styles.sectionBox}>
          <h3><Keyboard size={20} className={styles.icon} /> Interaction Biometrics</h3>
          <p>Your keystroke dynamics, interaction pacing, and usage velocity are tracked. We use this behavioral data to match the AI’s response delivery speed and tone to your current cognitive state.</p>
        </div>

        <div className={styles.sectionBox}>
          <h3><Database size={20} className={styles.icon} /> Omni-Channel Retention</h3>
          <p>Every query, click, and interaction is securely stored in our encrypted databases. This permanent memory ensures Tiflo AI never forgets a detail you've shared, enabling continuous, context-aware assistance.</p>
        </div>

        <div className={styles.sectionBox}>
          <h3><Lock size={20} className={styles.icon} /> Enterprise-Grade Security</h3>
          <p>Despite our extensive data collection, your information is protected by state-of-the-art AES-256 encryption. We do not sell your personal queries to third-party ad networks. Your data remains strictly within the Assudani Group ecosystem.</p>
        </div>
      </div>
    </PageContainer>
  );
}
