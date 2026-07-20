export const API_BASE = 'https://tiflo-ai.piyushassudani.in';

export const sendChatMessage = async (
  message: string, 
  isUncensored: boolean, 
  isIncognito: boolean,
  onChunk: (chunk: string) => void
) => {
  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message,
        mode: isIncognito ? 'incognito' : (isUncensored ? 'uncensored' : 'default'),
        use_openrouter: isUncensored,
        is_incognito: isIncognito
      })
    });

    if (!response.ok) throw new Error('Network response was not ok');
    if (!response.body) throw new Error('ReadableStream not supported');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (!line.trim()) continue;
        
        // Handle properly prefixed SSE lines
        if (line.startsWith('data:')) {
          // SSE spec: strip one leading space if present
          let dataStr = line.substring(5);
          if (dataStr.startsWith(' ')) dataStr = dataStr.substring(1);
          
          if (!dataStr) continue;
          if (dataStr.trim() === '[DONE]') continue;
          if (dataStr.startsWith('ACCOUNT:')) continue;
          if (dataStr.startsWith('__ACCOUNT__:')) continue;
          if (dataStr.startsWith('__STATUS__:')) continue;
          if (dataStr.startsWith('__SOURCES__:')) continue;
          if (dataStr.startsWith('__FOLLOWUPS__:')) continue;
          
          const text = dataStr.replace(/\\n/g, '\n');
          onChunk(text);
        }
        // Bare lines without data: prefix — skip metadata
        else if (line.startsWith('ACCOUNT:') || line.startsWith('__ACCOUNT__:')) {
          continue;
        }
      }
    }
  } catch (error) {
    console.error('Chat error:', error);
    onChunk('\n\n**Error:** Failed to connect to the Tiflo intelligence engine.');
  }
};
