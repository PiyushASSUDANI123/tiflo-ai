import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import 'katex/dist/katex.min.css';
import { User, Copy, Check } from 'lucide-react';
import styles from './ChatArea.module.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

const PROFANITY_MAP = [
  { p: /\bfuck\b/gi, r: 'f**k' },
  { p: /\bfucking\b/gi, r: 'f***ing' },
  { p: /\bfucker\b/gi, r: 'f***er' },
  { p: /\bfucked\b/gi, r: 'f***ed' },
  { p: /\bshit\b/gi, r: 's**t' },
  { p: /\bshitting\b/gi, r: 's***ing' },
  { p: /\bbitch\b/gi, r: 'b***h' },
  { p: /\bbitches\b/gi, r: 'b***hes' },
  { p: /\basshole\b/gi, r: 'a**hole' },
  { p: /\bbastard\b/gi, r: 'b***ard' },
  { p: /\bdick\b/gi, r: 'd**k' },
  { p: /\bcunt\b/gi, r: 'c**t' },
  { p: /\bwhore\b/gi, r: 'w***e' },
  { p: /\bslut\b/gi, r: 's**t' },
  { p: /\bbullshit\b/gi, r: 'b***shit' },
  { p: /\bprick\b/gi, r: 'p***k' },
  { p: /\bcock\b/gi, r: 'c**k' },
  { p: /\bdamn\b/gi, r: 'd**n' },
  { p: /\bcrap\b/gi, r: 'c**p' },
  { p: /\bbhenchod\b/gi, r: 'b*****d' },
  { p: /\bmadarchod\b/gi, r: 'm*****d' },
  { p: /\bchutiya\b/gi, r: 'c*****a' },
  { p: /\brandi\b/gi, r: 'r***i' },
  { p: /\bsaala\b/gi, r: 's***a' },
  { p: /\bkamina\b/gi, r: 'k****a' },
  { p: /\bharamzada\b/gi, r: 'h*******a' },
  { p: /\bbc\b/gi, r: 'b*' },
  { p: /\bmc\b/gi, r: 'm*' },
  { p: /\bkutte\b/gi, r: 'k***e' },
  { p: /\bkutta\b/gi, r: 'k***a' },
  { p: /\bbhosdike\b/gi, r: 'b******e' },
  { p: /\bbhosdiwale\b/gi, r: 'b********e' },
  { p: /\bbhosdiwala\b/gi, r: 'b********a' }
];

function censorText(text: string): string {
  let result = text;
  for (const { p, r } of PROFANITY_MAP) {
    result = result.replace(p, r);
  }
  return result;
}

const CodeBlock = ({ language, value }: { language: string, value: string }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={styles.codeBlockWrapper}>
      <div className={styles.codeHeader}>
        <span className={styles.codeLang}>{language}</span>
        <button className={styles.copyBtn} onClick={handleCopy}>
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span>{copied ? 'Copied!' : 'Copy'}</span>
        </button>
      </div>
      <SyntaxHighlighter
        style={vscDarkPlus as any}
        language={language}
        PreTag="div"
        customStyle={{ margin: 0, borderRadius: '0 0 8px 8px', background: '#1e1e1e' }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
};

export default function ChatArea({ messages, onPillClick }: { messages: Message[], onPillClick?: (text: string) => void }) {
  const pills = [
    "What can you do?",
    "Who created you?",
    "Write Python code",
    "Latest AI news",
    "Explain quantum computing"
  ];

  if (messages.length === 0) {
    return (
      <div className={styles.chatArea}>
        <div className={styles.emptyState}>
          <h1 className={styles.emptyLogo}>Tiflo AI</h1>
          <p className={styles.emptySubtitle}>Good to see you</p>
          <div className={styles.pillContainer}>
            {pills.map((pill, idx) => (
              <button 
                key={idx} 
                className={styles.pill}
                onClick={() => onPillClick?.(pill)}
              >
                {pill}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.chatArea}>
      {messages.map((msg) => (
        <div key={msg.id} className={`${styles.messageWrapper} ${msg.role === 'user' ? styles.user : styles.ai}`}>
          <div className={`${styles.message} ${msg.role === 'user' ? styles.user : styles.ai}`}>
            <div className={`${styles.avatar} ${msg.role === 'user' ? styles.user : styles.ai}`}>
              {msg.role === 'assistant' ? (
                <img src="/image.png" alt="AI" onError={(e) => (e.currentTarget.style.display = 'none')} />
              ) : (
                <User size={20} color="#fff" />
              )}
            </div>
            <div className={styles.content}>
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <CodeBlock
                        language={match[1]}
                        value={String(children).replace(/\n$/, '')}
                      />
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  }
                }}
              >
                {censorText(msg.content)}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
