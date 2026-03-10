import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, Send, MessageCircle, Home, Copy, RotateCcw, Check,
  ThumbsUp, ThumbsDown, Download, Maximize2, Minimize2,
  Clock, MoreVertical, ChevronDown, Sparkles
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ChatAgent.css';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  error?: boolean;
  feedback?: 'positive' | 'negative' | null;
  tokenCount?: number;
}

interface ChatAgentProps {
  currentPage?: string;
  hasAssessments?: boolean;
  workspaceId?: string;
}

const AVAILABLE_MODELS = [
  { id: 'claude-sonnet-4.5', label: 'Claude Sonnet 4.5', bedrock: 'us.anthropic.claude-3-5-sonnet-20241022-v2:0' },
  { id: 'claude-haiku-3.5', label: 'Claude Haiku 3.5', bedrock: 'us.anthropic.claude-3-5-haiku-20241022-v1:0' },
  { id: 'claude-opus-3', label: 'Claude Opus 3', bedrock: 'us.anthropic.claude-3-opus-20240229-v1:0' },
  { id: 'claude-sonnet-3', label: 'Claude Sonnet 3', bedrock: 'us.anthropic.claude-3-sonnet-20240229-v1:0' },
];

const QUICK_ACTIONS = [
  { label: 'Migration Risk Analysis', icon: '⚠️', query: 'Analyze migration risks for my database' },
  { label: 'Schema Compatibility', icon: '🔄', query: 'Check schema compatibility between databases' },
  { label: 'Create Assessment', icon: '📊', query: 'How do I create a new assessment?' },
  { label: 'View Reports', icon: '📄', query: 'How can I view assessment reports?' },
];

const SUGGESTED_QUERIES = [
  'How do I create a new assessment?',
  'What does schema analysis check?',
  'How do I run a compatibility check?',
  'Why is my assessment failing?',
  'How can I view assessment reports?',
  'What is data profiling used for?',
];

export const ChatAgent: React.FC<ChatAgentProps> = ({
  currentPage = 'dashboard',
  hasAssessments = true,
  workspaceId = 'default'
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationHistory, setConversationHistory] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [isFirstVisit, setIsFirstVisit] = useState(true);
  const [showHomeView, setShowHomeView] = useState(true);
  const [isMaximized, setIsMaximized] = useState(false);
  const [feedbackGiven, setFeedbackGiven] = useState<Set<string>>(new Set());
  const [selectedModel, setSelectedModel] = useState(AVAILABLE_MODELS[0]);
  const [showModelDropdown, setShowModelDropdown] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [totalInputTokens, setTotalInputTokens] = useState(0);
  const [totalOutputTokens, setTotalOutputTokens] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const moreMenuRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  useEffect(() => {
    if (isOpen && inputRef.current) setTimeout(() => inputRef.current?.focus(), 100);
  }, [isOpen]);

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => { if (e.key === 'Escape' && isOpen) toggleModal(); };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target as Node)) setShowModelDropdown(false);
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) setShowMoreMenu(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleSendMessage = async (messageText?: string, retryMessage?: Message) => {
    const text = messageText || inputValue.trim();
    if (!text || isLoading) return;

    let userMessage: Message;
    if (retryMessage) {
      userMessage = retryMessage;
    } else {
      userMessage = { id: Date.now().toString(), text, sender: 'user', timestamp: new Date() };
      setMessages(prev => [...prev, userMessage]);
      setConversationHistory(prev => [...prev, userMessage]);
    }

    setInputValue('');
    setIsLoading(true);
    setShowHomeView(false);

    // Estimate input tokens (rough: ~4 chars per token)
    const inputTokenEstimate = Math.round(text.length / 4);
    setTotalInputTokens(prev => prev + inputTokenEstimate);

    try {
      const recentHistory = conversationHistory.slice(-5).map(msg => ({
        role: msg.sender === 'user' ? 'user' : 'assistant',
        content: msg.text
      }));

      const response = await fetch('/api/chatagent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          context: currentPage,
          workspaceId,
          conversationHistory: recentHistory,
          model: selectedModel.bedrock
        })
      });

      if (!response.ok) throw new Error('Failed to get response');
      const data = await response.json();

      const responseText = data.response || 'I encountered an error. Please try again.';
      const outputTokenEstimate = Math.round(responseText.length / 4);
      setTotalOutputTokens(prev => prev + outputTokenEstimate);

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: responseText,
        sender: 'ai',
        timestamp: new Date(),
        tokenCount: outputTokenEstimate
      };

      setMessages(prev => [...prev, aiMessage]);
      setConversationHistory(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('ChatAgent error:', error);
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        text: 'Something went wrong. Please try again.',
        sender: 'ai', timestamp: new Date(), error: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = (message: Message) => {
    const idx = messages.findIndex(m => m.id === message.id);
    if (idx > 0 && messages[idx - 1].sender === 'user') {
      setMessages(prev => prev.filter(m => m.id !== message.id));
      handleSendMessage(messages[idx - 1].text, messages[idx - 1]);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); }
  };

  const handleFeedback = (messageId: string, feedback: 'positive' | 'negative') => {
    setMessages(prev => prev.map(msg => msg.id === messageId ? { ...msg, feedback } : msg));
    setFeedbackGiven(prev => new Set(prev).add(messageId));
  };

  const handleCopyMessage = async (messageId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) { console.error('Failed to copy:', err); }
  };

  const handleExportChat = () => {
    const chatText = messages.map(msg => `[${msg.sender.toUpperCase()}] ${msg.text}`).join('\n\n');
    const blob = new Blob([chatText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-export-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleBackToHome = () => {
    setMessages([]); setConversationHistory([]);
    setShowHomeView(true); setInputValue('');
    setTotalInputTokens(0); setTotalOutputTokens(0);
  };

  const toggleModal = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      setIsFirstVisit(false);
      if (messages.length === 0 && conversationHistory.length === 0) {
        setMessages([{
          id: 'welcome', sender: 'ai', timestamp: new Date(),
          text: "Hello! I'm your AI Migration Assistant. I can help you with migration planning, schema analysis, compatibility checks, and more. How can I assist you today?"
        }]);
        setShowHomeView(true);
      }
    }
  };

  const sanitizeText = (text: string) => text.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

  const formatTokens = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toString();

  return (
    <>
      {/* Floating Button */}
      <div className="chat-agent-container">
        <button
          className={`chat-agent-button ${!hasAssessments && isFirstVisit ? 'pulse' : ''}`}
          onClick={toggleModal}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          aria-label="Open AI Migration Assistant"
          aria-expanded={isOpen}
        >
          <Sparkles size={22} />
        </button>
        {showTooltip && !isOpen && (
          <div className="chat-agent-tooltip" role="tooltip">AI Migration Assistant</div>
        )}
      </div>

      {/* Modal */}
      {isOpen && (
        <>
          <div className="chat-agent-overlay" onClick={toggleModal} aria-hidden="true" />
          <div
            ref={modalRef}
            className={`chat-agent-modal ${isOpen ? 'open' : ''} ${isMaximized ? 'maximized' : ''}`}
            role="dialog" aria-modal="true" aria-labelledby="chat-agent-title"
          >
            {/* Header Bar */}
            <div className="chat-agent-header">
              <div className="chat-agent-header-left">
                <div className="chat-agent-logo-icon" aria-hidden="true">
                  <Sparkles size={18} />
                </div>
                <div className="chat-agent-title-group">
                  <span className="chat-agent-title" id="chat-agent-title">AI Migration Assistant</span>
                  <div className="chat-agent-token-badges">
                    <span className="token-badge">In: {formatTokens(totalInputTokens)}</span>
                    <span className="token-badge">Out: {formatTokens(totalOutputTokens)}</span>
                  </div>
                </div>
              </div>

              <div className="chat-agent-header-right">
                <button className="chat-agent-action-btn" onClick={handleBackToHome} title="New Chat" aria-label="New Chat">
                  <Clock size={16} />
                </button>

                {/* Model Selector */}
                <div className="model-selector-wrapper" ref={modelDropdownRef}>
                  <button
                    className="model-selector-btn"
                    onClick={() => setShowModelDropdown(!showModelDropdown)}
                    aria-label="Select model"
                  >
                    <span className="model-selector-icon">A</span>
                    <span className="model-selector-label">{selectedModel.label}</span>
                    <ChevronDown size={14} className={showModelDropdown ? 'rotated' : ''} />
                  </button>
                  {showModelDropdown && (
                    <div className="model-selector-dropdown">
                      {AVAILABLE_MODELS.map(model => (
                        <button
                          key={model.id}
                          className={`model-option ${model.id === selectedModel.id ? 'active' : ''}`}
                          onClick={() => { setSelectedModel(model); setShowModelDropdown(false); }}
                        >
                          <span className="model-option-icon">A</span>
                          <span>{model.label}</span>
                          {model.id === selectedModel.id && <Check size={14} />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* More Menu */}
                <div className="more-menu-wrapper" ref={moreMenuRef}>
                  <button className="chat-agent-action-btn" onClick={() => setShowMoreMenu(!showMoreMenu)} title="More options">
                    <MoreVertical size={16} />
                  </button>
                  {showMoreMenu && (
                    <div className="more-menu-dropdown">
                      <button onClick={() => { handleExportChat(); setShowMoreMenu(false); }}>
                        <Download size={14} /> Export Chat
                      </button>
                      <button onClick={() => { handleBackToHome(); setShowMoreMenu(false); }}>
                        <Home size={14} /> New Chat
                      </button>
                    </div>
                  )}
                </div>
                <button className="chat-agent-action-btn" onClick={() => setIsMaximized(!isMaximized)}
                  title={isMaximized ? "Minimize" : "Maximize"} aria-label={isMaximized ? "Minimize" : "Maximize"}>
                  {isMaximized ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
                </button>
                <button className="chat-agent-close" onClick={toggleModal} aria-label="Close chat">
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="chat-agent-body">
              {/* Quick Actions */}
              {messages.length <= 1 && !isLoading && (
                <div className="quick-actions">
                  {QUICK_ACTIONS.map((action, i) => (
                    <button key={i} className="quick-action-btn" onClick={() => handleSendMessage(action.query)}>
                      <span>{action.icon}</span><span>{action.label}</span>
                    </button>
                  ))}
                </div>
              )}

              {/* Messages */}
              <div className="chat-agent-messages" role="log" aria-live="polite">
                {messages.map((message) => (
                  <div key={message.id} className={`chat-message ${message.sender} ${message.error ? 'error' : ''}`}>
                    <div className="chat-message-bubble">
                      {message.sender === 'ai' ? (
                        <div className="chat-message-content">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              p: ({node, ...props}) => <p className="markdown-p" {...props} />,
                              ul: ({node, ...props}) => <ul className="markdown-ul" {...props} />,
                              ol: ({node, ...props}) => <ol className="markdown-ol" {...props} />,
                              li: ({node, ...props}) => <li className="markdown-li" {...props} />,
                              h2: ({node, ...props}) => <h2 className="markdown-h2" {...props} />,
                              h3: ({node, ...props}) => <h3 className="markdown-h3" {...props} />,
                              code: ({node, ...props}) => {
                                const isInline = !props.className;
                                return isInline ?
                                  <code className="markdown-code-inline" {...props} /> :
                                  <code className="markdown-code-block" {...props} />;
                              },
                              strong: ({node, ...props}) => <strong className="markdown-strong" {...props} />,
                            }}
                          >
                            {sanitizeText(message.text)}
                          </ReactMarkdown>

                          {/* Message Footer */}
                          <div className="message-footer">
                            <span className="message-time">
                              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            {message.tokenCount && (
                              <span className="message-tokens">{message.tokenCount} tokens</span>
                            )}
                            <div className="message-actions">
                              <button onClick={() => handleCopyMessage(message.id, message.text)} title="Copy">
                                {copiedMessageId === message.id ? <Check size={13} /> : <Copy size={13} />}
                              </button>
                              <button
                                className={message.feedback === 'positive' ? 'active' : ''}
                                onClick={() => handleFeedback(message.id, 'positive')}
                                disabled={feedbackGiven.has(message.id)} title="Helpful"
                              >
                                <ThumbsUp size={13} />
                              </button>
                              <button
                                className={message.feedback === 'negative' ? 'active' : ''}
                                onClick={() => handleFeedback(message.id, 'negative')}
                                disabled={feedbackGiven.has(message.id)} title="Not helpful"
                              >
                                <ThumbsDown size={13} />
                              </button>
                              {message.error && (
                                <button onClick={() => handleRetry(message)} title="Retry">
                                  <RotateCcw size={13} />
                                </button>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : (
                        <>
                          {message.text}
                          <div className="message-footer user-footer">
                            <span className="message-time">
                              {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                ))}

                {isLoading && (
                  <div className="chat-message ai">
                    <div className="chat-message-bubble typing" aria-label="AI is typing">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Suggestions */}
              {showHomeView && messages.length <= 1 && !isLoading && (
                <div className="chat-agent-suggestions">
                  <h4>Popular Questions</h4>
                  <div className="suggestions-grid">
                    {SUGGESTED_QUERIES.map((query, i) => (
                      <button key={i} className="suggestion-chip" onClick={() => handleSendMessage(query)}>{query}</button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="chat-agent-input-area">
              <div className="chat-agent-input-wrapper">
                <input
                  ref={inputRef} type="text" className="chat-agent-input"
                  placeholder="Ask about this feature..."
                  value={inputValue} onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown} disabled={isLoading}
                  aria-label="Type your message"
                />
                <button className="chat-agent-send" onClick={() => handleSendMessage()}
                  disabled={!inputValue.trim() || isLoading} aria-label="Send message">
                  <Send size={18} />
                </button>
              </div>
              <div className="chat-agent-footer-text">
                AI assistant trained on best practices of migration. Any feedback please <a href="mailto:support@shellkode.com">submit here</a>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
};
