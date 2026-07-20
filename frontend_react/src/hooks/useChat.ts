import { useState, useCallback, useEffect } from 'react';
import { sendChatMessage } from '../utils/api';
import { useChatHistory } from './useChatHistory';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export const useChat = (isIncognito: boolean = false) => {
  const [isStreaming, setIsStreaming] = useState(false);
  const history = useChatHistory();
  const [incognitoMessages, setIncognitoMessages] = useState<Message[]>([]);

  // When we switch *into* incognito, clear the ephemeral messages so it starts fresh
  useEffect(() => {
    if (isIncognito) {
      setIncognitoMessages([]);
    }
  }, [isIncognito]);

  const messages = isIncognito ? incognitoMessages : (history.activeSession?.messages ?? []);

  const sendMessage = useCallback(async (text: string, isUncensored: boolean) => {
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: text };
    
    if (isIncognito) {
      setIncognitoMessages(prev => [...prev, userMsg]);
    } else {
      history.ensureSession();
      history.updateMessages(prev => [...prev, userMsg]);
    }

    setIsStreaming(true);

    const aiMsgId = (Date.now() + 1).toString();

    if (isIncognito) {
      setIncognitoMessages(prev => [...prev, { id: aiMsgId, role: 'assistant', content: '' }]);
    } else {
      history.updateMessages(prev => [...prev, { id: aiMsgId, role: 'assistant', content: '' }]);
    }

    // Stream chunks into the AI message
    await sendChatMessage(text, isUncensored, isIncognito, (chunk) => {
      if (isIncognito) {
        setIncognitoMessages(prev =>
          prev.map(msg =>
            msg.id === aiMsgId ? { ...msg, content: msg.content + chunk } : msg
          )
        );
      } else {
        history.updateMessages(prev =>
          prev.map(msg =>
            msg.id === aiMsgId ? { ...msg, content: msg.content + chunk } : msg
          )
        );
      }
    });

    setIsStreaming(false);
  }, [history, isIncognito]);

  const clearChat = useCallback(() => {
    if (isIncognito) {
      setIncognitoMessages([]);
    } else {
      history.clearActiveSession();
    }
  }, [history, isIncognito]);

  return {
    messages,
    sendMessage,
    clearChat,
    isStreaming,
    // Expose history controls for the Sidebar
    sessions: history.sessions,
    activeId: history.activeId,
    startNewSession: history.startNewSession,
    switchSession: history.switchSession,
    deleteSession: history.deleteSession,
  };
};
