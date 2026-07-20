import { useState, useRef } from 'react';
import { Plus, Paperclip, Mic, ArrowUp } from 'lucide-react';
import styles from './InputBox.module.css';

interface InputBoxProps {
  onSendMessage: (text: string) => void;
  disabled?: boolean;
}

export default function InputBox({ onSendMessage, disabled }: InputBoxProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  };

  const handleSend = () => {
    if (!text.trim() || disabled) return;
    onSendMessage(text);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.inputContainer}>
      <div className={styles.inputWrapper}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={text}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Message Tiflo AI..."
          rows={1}
        />
        <div className={styles.controls}>
          <div className={styles.leftControls}>
            <button className={styles.toolsBtn}>
              <Plus size={14} />
              Tools
            </button>
            <button className={styles.iconBtn} title="Attach file">
              <Paperclip size={16} />
            </button>
            <button className={styles.iconBtn} title="Use Microphone">
              <Mic size={16} />
            </button>
          </div>
          <button 
            className={styles.sendBtn} 
            disabled={!text.trim() || disabled} 
            onClick={handleSend}
          >
            Send <ArrowUp size={14} />
          </button>
        </div>
      </div>
      <span className={styles.footerText}>
        Tiflo AI can make mistakes. Consider checking important information.
      </span>
    </div>
  );
}
