/**
 * useChatHistory — persists all chat sessions to localStorage.
 *
 * Data shape in localStorage key "tiflo_chat_sessions":
 *   ChatSession[]
 *
 * Active session key: "tiflo_active_session"
 */
import { useState, useCallback, useEffect } from 'react';
import type { Message } from './useChat';

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

const SESSIONS_KEY = 'tiflo_chat_sessions';
const ACTIVE_KEY = 'tiflo_active_session';

function loadSessions(): ChatSession[] {
  try {
    return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
  } catch { return []; }
}

function saveSessions(sessions: ChatSession[]) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

function deriveTitle(messages: Message[]): string {
  const first = messages.find(m => m.role === 'user');
  if (!first) return 'New chat';
  const text = first.content.trim();
  return text.length > 42 ? text.slice(0, 42) + '…' : text;
}

function newSession(): ChatSession {
  return {
    id: Date.now().toString(),
    title: 'New chat',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
}

export function useChatHistory() {
  const [sessions, setSessions] = useState<ChatSession[]>(loadSessions);
  const [activeId, setActiveId] = useState<string>(() => {
    return localStorage.getItem(ACTIVE_KEY) || '';
  });

  // Persist sessions whenever they change
  useEffect(() => {
    saveSessions(sessions);
  }, [sessions]);

  // Persist active ID
  useEffect(() => {
    if (activeId) localStorage.setItem(ACTIVE_KEY, activeId);
  }, [activeId]);

  // Current session (or create one on demand)
  const activeSession: ChatSession | undefined = sessions.find(s => s.id === activeId);

  // Ensure there's always at least one session
  const ensureSession = useCallback((): ChatSession => {
    if (activeSession) return activeSession;
    const fresh = newSession();
    setSessions(prev => [fresh, ...prev]);
    setActiveId(fresh.id);
    return fresh;
  }, [activeSession]);

  const updateMessages = useCallback((updater: (prev: Message[]) => Message[]) => {
    setSessions(prev => prev.map(s => {
      if (s.id !== activeId) return s;
      const nextMsgs = updater(s.messages);
      return {
        ...s,
        messages: nextMsgs,
        title: deriveTitle(nextMsgs),
        updatedAt: Date.now(),
      };
    }));
  }, [activeId]);

  const startNewSession = useCallback(() => {
    const fresh = newSession();
    setSessions(prev => [fresh, ...prev]);
    setActiveId(fresh.id);
    return fresh;
  }, []);

  const switchSession = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      if (activeId === id) {
        const nextId = next[0]?.id;
        if (nextId) setActiveId(nextId);
        else {
          const fresh = newSession();
          next.unshift(fresh);
          setActiveId(fresh.id);
        }
      }
      return next;
    });
  }, [activeId]);

  const clearActiveSession = useCallback(() => {
    setSessions(prev => prev.map(s =>
      s.id === activeId ? { ...s, messages: [], title: 'New chat', updatedAt: Date.now() } : s
    ));
  }, [activeId]);

  return {
    sessions,
    activeSession,
    activeId,
    ensureSession,
    updateMessages,
    startNewSession,
    switchSession,
    deleteSession,
    clearActiveSession,
  };
}
