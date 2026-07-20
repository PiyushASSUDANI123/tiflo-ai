import { X, ExternalLink, RefreshCw } from 'lucide-react';
import { useRef } from 'react';
import styles from './TerminalPanel.module.css';

interface TerminalPanelProps {
  open: boolean;
  onClose: () => void;
  inline?: boolean;
}

export default function TerminalPanel({ open, onClose, inline = false }: TerminalPanelProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const refresh = () => {
    if (iframeRef.current) {
      iframeRef.current.src = iframeRef.current.src;
    }
  };

  const content = (
    <>
      {/* Header bar */}
      <div className={styles.panelHeader}>
        <div className={styles.panelTitle}>
          <span className={styles.dot} />
          <span>PyPocket IDE</span>
          <span className={styles.subtitle}>pypocket.xyz</span>
        </div>
        <div className={styles.panelActions}>
          <button onClick={refresh} title="Refresh">
            <RefreshCw size={13} />
          </button>
          <a
            href="https://pypocket.xyz"
            target="_blank"
            rel="noopener noreferrer"
            title="Open in new tab"
            className={styles.actionLink}
          >
            <ExternalLink size={13} />
          </a>
          <button onClick={onClose} title="Close">
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Embedded iframe */}
      <iframe
        ref={iframeRef}
        src="https://pypocket.xyz"
        className={styles.iframe}
        title="PyPocket IDE"
        allow="clipboard-read; clipboard-write"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
      />
    </>
  );

  if (inline) {
    return (
      <aside className={`${styles.inlinePanel} ${open ? styles.inlinePanelOpen : ''}`}>
        {content}
      </aside>
    );
  }

  return null;
}
