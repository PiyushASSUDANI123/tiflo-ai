import { Sidebar as SidebarIcon, Plus, Download, Terminal, Share2, Trash2, HelpCircle } from 'lucide-react';
import styles from './Header.module.css';

interface HeaderProps {
  onToggleSidebar?: () => void;
  isUncensored: boolean;
  setIsUncensored: (val: boolean) => void;
  onClearChat?: () => void;
  onDownload?: () => void;
  onShare?: () => void;
  onOpenTerminal?: () => void;
  terminalOpen?: boolean;
}

export default function Header({ 
  onToggleSidebar, 
  isUncensored, 
  setIsUncensored,
  onClearChat,
  onDownload,
  onShare,
  onOpenTerminal,
  terminalOpen = false
}: HeaderProps) {

  return (
    <>
      <header className={styles.header}>
        <div className={styles.leftControls}>
          <button className={styles.iconBtn} onClick={onToggleSidebar} title="Toggle sidebar">
            <SidebarIcon size={20} />
          </button>
          <button className={styles.iconBtn} onClick={onClearChat} title="New Chat">
            <Plus size={20} />
          </button>

          {/* UNCENSORED toggle — actually wired up */}
          <button
            className={`${styles.uncensoredToggle} ${isUncensored ? styles.uncensoredActive : ''}`}
            onClick={() => setIsUncensored(!isUncensored)}
            title={isUncensored ? 'Switch to Standard mode' : 'Enable Uncensored mode'}
          >
            <div className={`${styles.toggleSwitch} ${isUncensored ? styles.toggleOn : ''}`}>
              <div className={styles.toggleThumb} />
            </div>
            <span className={styles.toggleLabel}>UNCENSORED</span>
          </button>
        </div>

        <div className={styles.rightControls}>
          {/* Record dot */}
          <button className={`${styles.actionIcon} ${styles.recordIcon}`} title="Voice (coming soon)">
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'currentColor' }} />
          </button>

          <button className={styles.actionIcon} onClick={onDownload} title="Download Chat">
            <Download size={18} />
          </button>

          {/* Terminal — toggles split panel */}
          <button
            className={`${styles.actionIcon} ${styles.terminalIcon} ${terminalOpen ? styles.terminalActive : ''}`}
            onClick={onOpenTerminal}
            title={terminalOpen ? 'Close Terminal' : 'Open Terminal'}
          >
            <Terminal size={18} />
          </button>

          <button className={styles.actionIcon} onClick={onShare} title="Share Chat">
            <Share2 size={18} />
          </button>
          <button className={`${styles.actionIcon} ${styles.trashIcon}`} onClick={onClearChat} title="Clear Chat">
            <Trash2 size={18} />
          </button>
          <button className={styles.actionIcon} title="Help">
            <HelpCircle size={18} />
          </button>
        </div>
      </header>
    </>
  );
}
