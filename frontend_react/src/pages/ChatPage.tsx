import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import Header from '../components/Header';
import ChatArea from '../components/ChatArea';
import InputBox from '../components/InputBox';
import TerminalPanel from '../components/TerminalPanel';
import styles from './ChatPage.module.css';
import { useChat } from '../hooks/useChat';
import type { AppContextType } from '../App';

export default function ChatPage() {
  const [isIncognito, setIsIncognito] = useState(false);

  const {
    messages,
    sendMessage,
    clearChat,
    isStreaming,
    sessions,
    activeId,
    startNewSession,
    switchSession,
    deleteSession,
  } = useChat(isIncognito);

  const [isUncensored, setIsUncensored] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const { toggleSidebar, setSidebarProps } = useOutletContext<AppContextType>();

  // Sync history props into App context (only when they actually change)
  useEffect(() => {
    if (setSidebarProps) {
      setSidebarProps({ 
        sessions, 
        activeId, 
        startNewSession, 
        switchSession, 
        deleteSession,
        incognito: isIncognito,
        setIncognito: setIsIncognito
      });
    }
  }, [sessions, activeId, isIncognito]); // eslint-disable-line

  const handleDownload = () => {
    if (messages.length === 0) return;
    const content = messages.map(m => `${m.role.toUpperCase()}:\n${m.content}`).join('\n\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tiflo-ai-chat-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleShare = () => {
    if (messages.length === 0) return;
    const content = messages.map(m => `${m.role.toUpperCase()}:\n${m.content}`).join('\n\n');
    navigator.clipboard.writeText(content).then(() => {
      alert('Chat copied to clipboard!');
    });
  };

  const handleNewChat = () => {
    setIsIncognito(false);
    startNewSession();
  };

  return (
    <div className={`${styles.chatPage} ${terminalOpen ? styles.withTerminal : ''}`}>
      <div className={styles.chatColumn}>
        <Header
          onToggleSidebar={toggleSidebar}
          isUncensored={isUncensored}
          setIsUncensored={setIsUncensored}
          onClearChat={handleNewChat}
          onDownload={handleDownload}
          onShare={handleShare}
          onOpenTerminal={() => setTerminalOpen(v => !v)}
          terminalOpen={terminalOpen}
        />
        <ChatArea
          messages={messages}
          onPillClick={(text) => sendMessage(text, isUncensored, isIncognito)}
        />
        <InputBox
          onSendMessage={(text) => sendMessage(text, isUncensored, isIncognito)}
          disabled={isStreaming}
        />
      </div>

      <TerminalPanel
        open={terminalOpen}
        onClose={() => setTerminalOpen(false)}
        inline
      />
    </div>
  );
}
