import { useState, useCallback } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import styles from './App.module.css';
import type { ChatSession } from './hooks/useChatHistory';

export interface SidebarProps {
  sessions: ChatSession[];
  activeId: string;
  startNewSession: () => void;
  switchSession: (id: string) => void;
  deleteSession: (id: string) => void;
  incognito: boolean;
  setIncognito: (v: boolean) => void;
}

export type AppContextType = {
  toggleSidebar: () => void;
  isSidebarOpen: boolean;
  setSidebarProps: (props: SidebarProps) => void;
};

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [sidebarProps, setSidebarPropsState] = useState<SidebarProps>({
    sessions: [],
    activeId: '',
    startNewSession: () => {},
    switchSession: () => {},
    deleteSession: () => {},
    incognito: false,
    setIncognito: () => {},
  });

  const toggleSidebar = () => setIsSidebarOpen(v => !v);

  const setSidebarProps = useCallback((props: SidebarProps) => {
    setSidebarPropsState(props);
  }, []);

  return (
    <div className={styles.appContainer}>
      <div className={`${styles.sidebarWrapper} ${!isSidebarOpen ? styles.collapsed : ''}`}>
        <Sidebar {...sidebarProps} />
      </div>
      <main className={styles.mainContent}>
        <Outlet context={{ toggleSidebar, isSidebarOpen, setSidebarProps }} />
      </main>
    </div>
  );
}

export default App;
