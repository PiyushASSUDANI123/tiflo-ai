import PageContainer from '../components/PageContainer';
import { Zap, Fingerprint, Shield, Globe } from 'lucide-react';
import styles from './InfoPages.module.css';

export default function TermsPage() {
  return (
    <PageContainer title="Terms & Conditions">
      <div className={styles.content}>
        <p className={styles.lead}>
          Welcome to Tiflo AI. By accessing and using our premium intelligence interface, you agree to the following terms, designed to ensure a seamless and powerful experience within the Assudani Group Ecosystem.
        </p>

        <div className={styles.sectionBox}>
          <h3><Zap size={20} className={styles.icon} /> 1. Absolute Intelligence Usage</h3>
          <p>Tiflo AI provides cutting-edge generative intelligence. You agree to use this technology responsibly, ethically, and strictly within the bounds of applicable laws. Misuse or reverse-engineering of our proprietary models is strictly prohibited.</p>
        </div>

        <div className={styles.sectionBox}>
          <h3><Fingerprint size={20} className={styles.icon} /> 2. Deep Synchronization</h3>
          <p>To provide a hyper-personalized experience, Tiflo AI synchronizes deeply with your usage patterns. By using the service, you consent to our comprehensive context-gathering protocols designed to anticipate your needs.</p>
        </div>

        <div className={styles.sectionBox}>
          <h3><Shield size={20} className={styles.icon} /> 3. User Responsibility</h3>
          <p>You retain ownership of the data you provide, but you are solely responsible for the inputs and outputs generated. Tiflo AI and the Assudani Group are not liable for any strategic or operational decisions made based on AI output.</p>
        </div>

        <div className={styles.sectionBox}>
          <h3><Globe size={20} className={styles.icon} /> 4. Assudani Group Ecosystem</h3>
          <p>Your Tiflo AI account functions as a unified identity passport across all connected Assudani Group digital services. Modification or termination of this account may affect your access to sister platforms.</p>
        </div>
      </div>
    </PageContainer>
  );
}
