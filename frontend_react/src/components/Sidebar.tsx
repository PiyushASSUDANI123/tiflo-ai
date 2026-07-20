import { useState } from 'react';
import { Plus, Settings, User, Trash2, MessageSquare } from 'lucide-react';
import styles from './Sidebar.module.css';
import type { ChatSession } from '../hooks/useChatHistory';

interface SidebarComponentProps {
  sessions: ChatSession[];
  activeId: string;
  startNewSession: () => void;
  switchSession: (id: string) => void;
  deleteSession: (id: string) => void;
  incognito?: boolean;
  setIncognito?: (v: boolean) => void;
}

function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return new Date(ts).toLocaleDateString();
}

// Group sessions by date
function groupSessions(sessions: ChatSession[]) {
  const today: ChatSession[] = [];
  const yesterday: ChatSession[] = [];
  const older: ChatSession[] = [];
  const now = Date.now();

  for (const s of sessions) {
    const diff = now - s.updatedAt;
    if (diff < 86400000) today.push(s);
    else if (diff < 172800000) yesterday.push(s);
    else older.push(s);
  }
  return { today, yesterday, older };
}

export default function Sidebar({
  sessions,
  activeId,
  startNewSession,
  switchSession,
  deleteSession,
  incognito = false,
  setIncognito,
}: SidebarComponentProps) {
  const [localIncognito, setLocalIncognito] = useState(false);
  const isIncognito = setIncognito ? incognito : localIncognito;
  const toggleIncognito = () => {
    if (setIncognito) setIncognito(!incognito);
    else setLocalIncognito(!localIncognito);
  };
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const { today, yesterday, older } = groupSessions(
    sessions.filter(s => s.messages.length > 0)
  );

  const renderGroup = (label: string, items: ChatSession[]) => {
    if (items.length === 0) return null;
    return (
      <div key={label} className={styles.group}>
        <span className={styles.groupLabel}>{label}</span>
        {items.map(s => (
          <div
            key={s.id}
            className={`${styles.historyItem} ${s.id === activeId ? styles.historyItemActive : ''}`}
            onClick={() => {
              if (setIncognito) setIncognito(false);
              switchSession(s.id);
            }}
            onMouseEnter={() => setHoveredId(s.id)}
            onMouseLeave={() => setHoveredId(null)}
          >
            <MessageSquare size={14} className={styles.historyIcon} />
            <div className={styles.historyText}>
              <span className={styles.historyTitle}>{s.title}</span>
              <span className={styles.historyTime}>{formatRelativeTime(s.updatedAt)}</span>
            </div>
            {hoveredId === s.id && (
              <button
                className={styles.deleteBtn}
                onClick={e => { e.stopPropagation(); deleteSession(s.id); }}
                title="Delete"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <aside className={styles.sidebar}>
      {/* TOP */}
      <div className={styles.top}>
        <div className={styles.header}>
          <div className={styles.logoWrap}>
            <img src="/logo.png" alt="Tiflo AI" className={styles.logoImg} />
            <span className={styles.logoText}>Tiflo AI</span>
            <span className={styles.badge}>v1.0.1</span>
          </div>
        </div>

        <button className={styles.newChatBtn} onClick={() => {
          if (setIncognito) setIncognito(false);
          startNewSession();
        }}>
          <Plus size={16} />
          New chat
        </button>
      </div>

      {/* MIDDLE: Chat History */}
      <div className={styles.historyList}>
        {sessions.filter(s => s.messages.length > 0).length === 0 ? (
          <div className={styles.emptyHistory}>
            <MessageSquare size={28} opacity={0.15} />
            <span>No chats yet</span>
          </div>
        ) : (
          <>
            {renderGroup('Today', today)}
            {renderGroup('Yesterday', yesterday)}
            {renderGroup('Earlier', older)}
          </>
        )}
      </div>

      {/* BOTTOM */}
      <div className={styles.footer}>
        <div
          className={styles.incognitoCard}
          onClick={toggleIncognito}
        >
          <div className={styles.incognitoInfo}>
            <span className={styles.incognitoIcon}>🕵️</span>
            <div className={styles.incognitoTexts}>
              <span className={styles.incognitoTitle}>Incognito Mode</span>
              <span className={styles.incognitoSub}>Stealth Chat (Not Saved)</span>
            </div>
          </div>
          <div className={styles.toggleSwitch} data-on={isIncognito}>
            <div className={styles.toggleThumb} />
          </div>
        </div>

        <div className={styles.userRow}>
          <div className={styles.userInfo}>
            <div className={styles.avatar}>
              <User size={18} />
            </div>
            <div className={styles.userTexts}>
              <span className={styles.userName}>Guest User</span>
              <div className={styles.userLinks}>
                <span 
                  style={{ cursor: 'pointer', opacity: 0.7 }} 
                  onClick={() => window.open('https://piyushassudani.in', '_blank')}
                >
                  By Assudani Group
                </span>
              </div>
            </div>
          </div>
          <button className={styles.settingsBtn}>
            <Settings size={18} />
          </button>
        </div>
      </div>
    </aside>
  );
}
