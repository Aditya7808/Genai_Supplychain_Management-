import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  Wrench,
  ChevronDown,
  ChevronUp,
  TrendingUp,
  ArrowLeftRight,
  SlidersHorizontal,
  Copy,
  Check,
  CheckCircle2,
} from 'lucide-react';
import { marked } from 'marked';
import { ChatMessage } from '../types';
import { sendChatMessage } from '../api';

// Configure marked with GitHub-flavored markdown and line breaks
marked.setOptions({
  gfm: true,
  breaks: true,
});

interface ChatViewProps {
  initialSkuId?: string;
  initialWarehouseId?: string;
  onNavigate?: (tab: string, context?: { skuId?: string; warehouseId?: string }) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({
  initialSkuId,
  initialWarehouseId,
  onNavigate,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      content: `### Welcome to your GenAI Demand & Inventory Copilot
I pair statistical demand forecasting with domain context (festival calendars, supplier constraints, lead times, and inter-warehouse routes).

Ask me anything about your supply chain network:
- *"Analyze SKU_001 stock status in WH_01 (Delhi)"*
- *"Should I transfer surplus stock or place a supplier purchase order for SKU_005?"*
- *"How will upcoming festive sales impact demand in South India?"*`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (initialSkuId && initialWarehouseId) {
      handleSend(`Analyze inventory and replenishment options for ${initialSkuId} at ${initialWarehouseId}`);
    }
  }, [initialSkuId, initialWarehouseId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const resp = await sendChatMessage(query);
      const aiMsg: ChatMessage = {
        id: `ai-${Date.now()}`,
        sender: 'assistant',
        content: resp.reply,
        model_used: resp.model_used,
        tool_calls: resp.tool_calls,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        content: `Failed to retrieve AI response: ${err.message || 'Unknown network error'}. Please verify that the FastAPI backend server is running.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const toggleTools = (msgId: string) => {
    setExpandedTools((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const samplePrompts = [
    'Analyze SKU_001 stock status at WH_01 (Delhi)',
    'Check inter-warehouse transfer options for SKU_005',
    'What festivals are scheduled and which categories will surge?',
    'Simulate +30% demand shock on SKU_012 at WH_02',
  ];

  return (
    <div className="page-body">
      <div className="chat-wrapper">
        <div className="chat-messages">
          {messages.map((m) => {
            const isUser = m.sender === 'user';
            const hasTools = m.tool_calls && m.tool_calls.length > 0;
            const toolsExpanded = expandedTools[m.id];

            // Detect SKU and Warehouse for quick context actions
            const skuMatch = m.content.match(/SKU_\d+/i);
            const whMatch = m.content.match(/WH_\d+/i);
            const detectedSku = skuMatch ? skuMatch[0].toUpperCase() : undefined;
            const detectedWh = whMatch ? whMatch[0].toUpperCase() : undefined;

            return (
              <div key={m.id} className={`message-row ${isUser ? 'user' : ''}`}>
                <div className={`message-avatar ${isUser ? 'avatar-user' : 'avatar-ai'}`}>
                  {isUser ? <User size={18} /> : <Bot size={18} />}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxWidth: '100%', minWidth: 0 }}>
                  {/* Tool execution badge if tools were invoked */}
                  {hasTools && (
                    <div
                      style={{
                        background: 'rgba(99, 102, 241, 0.1)',
                        border: '1px solid rgba(99, 102, 241, 0.25)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '6px 12px',
                        fontSize: '12px',
                        color: '#a5b4fc',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                      onClick={() => toggleTools(m.id)}
                    >
                      <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <Wrench size={13} />
                        <span>Used {m.tool_calls!.length} analysis tools (Forecast, Inventory, Transfers)</span>
                      </span>
                      {toolsExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </div>
                  )}

                  {toolsExpanded && hasTools && (
                    <div
                      style={{
                        background: 'rgba(0, 0, 0, 0.35)',
                        padding: '10px 14px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '11px',
                        fontFamily: 'var(--font-mono)',
                        color: '#94a3b8',
                        border: '1px solid var(--border-glass)',
                      }}
                    >
                      {m.tool_calls!.map((t, idx) => (
                        <div key={idx} style={{ marginBottom: '6px' }}>
                          <span style={{ color: '#38bdf8' }}>&gt; {t.name}</span>
                          <span style={{ color: '#cbd5e1' }}>({JSON.stringify(t.args)})</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Main Message Bubble */}
                  <div className={`message-bubble ${isUser ? 'bubble-user' : 'bubble-ai'}`}>
                    <div
                      dangerouslySetInnerHTML={{
                        __html: renderMarkdownContent(m.content),
                      }}
                    />
                  </div>

                  {/* Action Bar for Assistant Messages */}
                  {!isUser && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        flexWrap: 'wrap',
                        gap: '8px',
                        padding: '2px 4px',
                      }}
                    >
                      {/* Left: Interactive Jump Chips */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        {detectedSku && onNavigate && (
                          <>
                            <button
                              className="chat-action-chip"
                              onClick={() =>
                                onNavigate('forecast', {
                                  skuId: detectedSku,
                                  warehouseId: detectedWh || 'WH_01',
                                })
                              }
                            >
                              <TrendingUp size={12} color="#38bdf8" />
                              <span>Forecast ({detectedSku})</span>
                            </button>
                            <button
                              className="chat-action-chip"
                              onClick={() =>
                                onNavigate('transfers', {
                                  skuId: detectedSku,
                                  warehouseId: detectedWh || 'WH_01',
                                })
                              }
                            >
                              <ArrowLeftRight size={12} color="#34d399" />
                              <span>Rebalance Stock</span>
                            </button>
                            <button
                              className="chat-action-chip"
                              onClick={() => onNavigate('whatif')}
                            >
                              <SlidersHorizontal size={12} color="#f59e0b" />
                              <span>Simulate Shock</span>
                            </button>
                          </>
                        )}
                      </div>

                      {/* Right: Timestamp, Model, & Copy */}
                      <div
                        style={{
                          fontSize: '11px',
                          color: 'var(--text-muted)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '10px',
                        }}
                      >
                        <span>{m.timestamp}</span>
                        {m.model_used && (
                          <span>• {m.model_used.replace(':free', '')}</span>
                        )}
                        <button
                          onClick={() => handleCopy(m.id, m.content)}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: copiedId === m.id ? '#34d399' : 'var(--text-muted)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            fontSize: '11px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                          }}
                          title="Copy message markdown"
                        >
                          {copiedId === m.id ? <Check size={12} /> : <Copy size={12} />}
                          <span>{copiedId === m.id ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                    </div>
                  )}

                  {isUser && (
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        alignSelf: 'flex-end',
                        padding: '0 4px',
                      }}
                    >
                      <span>{m.timestamp}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="message-row">
              <div className="message-avatar avatar-ai">
                <Sparkles size={18} />
              </div>
              <div className="message-bubble bubble-ai" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span className="badge-pulse" />
                <span style={{ color: 'var(--text-secondary)' }}>
                  GenAI reasoning active — retrieving festival calendar & simulating stockout probability...
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        <div
          style={{
            padding: '8px 20px',
            display: 'flex',
            gap: '8px',
            overflowX: 'auto',
            background: 'rgba(10, 15, 29, 0.6)',
            borderTop: '1px solid var(--border-glass)',
          }}
        >
          {samplePrompts.map((p, idx) => (
            <button
              key={idx}
              className="btn btn-secondary"
              style={{
                fontSize: '11px',
                padding: '4px 10px',
                whiteSpace: 'nowrap',
                borderRadius: 'var(--radius-full)',
              }}
              onClick={() => handleSend(p)}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="chat-input-box">
          <input
            type="text"
            className="chat-input"
            placeholder="Ask about demand forecasts, festival lifts, safety stock, or transfers..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
          />
          <button
            className="btn btn-primary"
            style={{ padding: '0 20px' }}
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
          >
            <Send size={16} />
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
};

// Clean and convert markdown and legacy raw RAG patterns into executive-ready HTML
function renderMarkdownContent(text: string): string {
  if (!text) return '';

  let cleaned = text;

  // 1. Clean up legacy raw text delimiters
  cleaned = cleaned.replace(/---\s*RELEVANT DOMAIN KNOWLEDGE & CALENDAR CONTEXT\s*---/gi, '');
  cleaned = cleaned.replace(/--------------------------------------------------/gi, '');

  // 2. Transform legacy [1] Type: promotion | Region: North patterns into clean bullet format
  cleaned = cleaned.replace(
    /\[\d+\]\s*Type:\s*([^\s|]+)\s*\|\s*Region:\s*([^\n\r]+)\s*\n+([^\[\n\r]+(?:\n+(?!\[\d+\])[^\n\r]+)*)/gi,
    (_, pType, pRegion, pBody) => {
      const typeLabel = pType.charAt(0).toUpperCase() + pType.slice(1).toLowerCase();
      const cleanBody = pBody.replace(/Promotion Campaign:\s*/i, '').trim();
      return `\n- **${typeLabel} Context — ${pRegion.trim()} Region**\n  ${cleanBody}\n\n`;
    }
  );

  // 3. Remove leftover bracketed tag artifacts (e.g. [PROMOTION] · North -> Promotion Context — North Region)
  cleaned = cleaned.replace(/\[([A-Z_]+)\]\s*(?:·|-)\s*/g, (_, tag) => {
    const formatted = tag.charAt(0).toUpperCase() + tag.slice(1).toLowerCase();
    return `**${formatted} Context** — `;
  });

  // 4. Strip emojis if present for clean professional presentation
  cleaned = cleaned.replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu, '');

  // 5. Render markdown via marked
  try {
    return marked.parse(cleaned, { gfm: true, breaks: true }) as string;
  } catch {
    return cleaned;
  }
}

