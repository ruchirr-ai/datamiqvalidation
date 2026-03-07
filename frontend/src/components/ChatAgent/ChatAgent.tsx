import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Send, MessageCircle, Home, Copy, RotateCcw, Check, ThumbsUp, ThumbsDown, Download, Maximize2, Minimize2 } from 'lucide-react';
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
}

interface ChatAgentProps {
  currentPage?: string;
  hasAssessments?: boolean;
  workspaceId?: string;
}

const SUGGESTED_QUERIES = [
  'How do I create a new assessment?',
  'What does schema analysis check?',
  'How do I run a compatibility check?',
  'Why is my assessment failing?',
  'How can I view assessment reports?',
  'What is data profiling used for?',
  'How do I connect BigQuery?',
  'How do I schedule assessment jobs?',
  'How do I fix schema mismatch issues?',
  'Where can I download assessment results?'
];

const QUICK_ACTIONS = [
  { label: 'Migration Risk Analysis', icon: '⚠️', query: 'Analyze migration risks for my database' },
  { label: 'Schema Compatibility', icon: '🔄', query: 'Check schema compatibility between databases' },
  { label: 'Create Assessment', icon: '📊', query: 'How do I create a new assessment?' },
  { label: 'View Reports', icon: '📄', query: 'How can I view assessment reports?' },
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
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        toggleModal();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(event.target as Node) && isOpen) {
        const target = event.target as HTMLElement;
        if (!target.closest('.chat-agent-button')) {
          toggleModal();
        }
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleSendMessage = async (messageText?: string, retryMessage?: Message) => {
    const text = messageText || inputValue.trim();
    if (!text || isLoading) return;

    let userMessage: Message;
    
    if (retryMessage) {
      // Retry failed message
      userMessage = retryMessage;
    } else {
      userMessage = {
        id: Date.now().toString(),
        text,
        sender: 'user',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, userMessage]);
      setConversationHistory(prev => [...prev, userMessage]);
    }

    setInputValue('');
    setIsLoading(true);
    setShowHomeView(false);

    try {
      // Get last 5 messages for context
      const recentHistory = conversationHistory.slice(-5).map(msg => ({
        role: msg.sender === 'user' ? 'user' : 'assistant',
        content: msg.text
      }));

      const response = await fetch('/api/chatagent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          context: currentPage,
          workspaceId: workspaceId,
          conversationHistory: recentHistory
        })
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();

      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: data.response || 'I apologize, but I encountered an error. Please try again.',
        sender: 'ai',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, aiMessage]);
      setConversationHistory(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('ChatAgent error:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Something went wrong. Please try again.',
        sender: 'ai',
        timestamp: new Date(),
        error: true
      };

      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = (message: Message) => {
    // Find the user message before this error
    const messageIndex = messages.findIndex(m => m.id === message.id);
    if (messageIndex > 0) {
      const userMessage = messages[messageIndex - 1];
      if (userMessage.sender === 'user') {
        // Remove error message
        setMessages(prev => prev.filter(m => m.id !== message.id));
        // Retry
        handleSendMessage(userMessage.text, userMessage);
      }
    }
  };

  const handleSuggestedQuery = (query: string) => {
    setInputValue(query);
    handleSendMessage(query);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleFeedback = (messageId: string, feedback: 'positive' | 'negative') => {
    setMessages(prev => prev.map(msg => 
      msg.id === messageId ? { ...msg, feedback } : msg
    ));
    setFeedbackGiven(prev => new Set(prev).add(messageId));
    
    // Log feedback for analytics
    console.log(`Feedback for message ${messageId}: ${feedback}`);
  };

  const handleExportChat = () => {
    const chatText = messages
      .map(msg => `[${msg.sender.toUpperCase()}] ${msg.text}`)
      .join('\n\n');
    
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

  const toggleMaximize = () => {
    setIsMaximized(!isMaximized);
  };

  const handleBackToHome = () => {
    setMessages([]);
    setConversationHistory([]);
    setShowHomeView(true);
    setInputValue('');
  };

  const handleCopyMessage = async (messageId: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedMessageId(messageId);
      setTimeout(() => setCopiedMessageId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const toggleModal = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      setIsFirstVisit(false);
      // Show welcome message only if no conversation history
      if (messages.length === 0 && conversationHistory.length === 0) {
        const welcomeMessage: Message = {
          id: 'welcome',
          text: 'Hello! I\'m your Assessment AI Assistant. I can help you with assessments, schema analysis, compatibility checks, reports, and data profiling. How can I assist you today?',
          sender: 'ai',
          timestamp: new Date()
        };
        setMessages([welcomeMessage]);
        setShowHomeView(true);
      }
    }
  };

  const sanitizeText = (text: string) => {
    // Basic XSS prevention
    return text.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
  };

  return (
    <>
      {/* Floating Button */}
      <div className="chat-agent-container">
        <button
          className={`chat-agent-button ${!hasAssessments && isFirstVisit ? 'pulse' : ''}`}
          onClick={toggleModal}
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          aria-label="Open AI Assistant"
          aria-expanded={isOpen}
        >
          <MessageCircle size={24} />
        </button>
        
        {showTooltip && !isOpen && (
          <div className="chat-agent-tooltip" role="tooltip">
            Ask AI Assistant
          </div>
        )}
      </div>

      {/* Modal */}
      {isOpen && (
        <>
          <div 
            className="chat-agent-overlay" 
            onClick={toggleModal}
            aria-hidden="true"
          />
          <div 
            ref={modalRef}
            className={`chat-agent-modal ${isOpen ? 'open' : ''} ${isMaximized ? 'maximized' : ''}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby="chat-agent-title"
          >
            {/* Header */}
            <div className="chat-agent-header">
              <div className="chat-agent-header-content">
                <div className="chat-agent-logo" aria-hidden="true">
                  <MessageCircle size={24} />
                </div>
                <div className="chat-agent-header-text">
                  <h3 id="chat-agent-title">Assessment AI Assistant</h3>
                  <p>Ask questions about assessments, schema, compatibility, reports, and profiling.</p>
                </div>
              </div>
              <div className="chat-agent-header-actions">
                {messages.length > 1 && (
                  <>
                    <button
                      className="chat-agent-action-btn"
                      onClick={handleExportChat}
                      aria-label="Export chat"
                      title="Export Chat"
                    >
                      <Download size={18} />
                    </button>
                    <button
                      className="chat-agent-action-btn"
                      onClick={handleBackToHome}
                      aria-label="Back to home"
                      title="New Chat"
                    >
                      <Home size={18} />
                    </button>
                  </>
                )}
                <button
                  className="chat-agent-action-btn"
                  onClick={toggleMaximize}
                  aria-label={isMaximized ? "Minimize" : "Maximize"}
                  title={isMaximized ? "Minimize" : "Maximize"}
                >
                  {isMaximized ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
                </button>
                <button
                  className="chat-agent-close"
                  onClick={toggleModal}
                  aria-label="Close chat"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            {/* Body */}
            <div className="chat-agent-body">
              {/* Quick Actions - Show when no messages */}
              {messages.length <= 1 && !isLoading && (
                <div className="quick-actions">
                  {QUICK_ACTIONS.map((action, index) => (
                    <button
                      key={index}
                      className="quick-action-btn"
                      onClick={() => handleSuggestedQuery(action.query)}
                      aria-label={action.label}
                    >
                      <span>{action.icon}</span>
                      <span>{action.label}</span>
                    </button>
                  ))}
                </div>
              )}
              
              {/* Messages */}
              <div className="chat-agent-messages" role="log" aria-live="polite">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`chat-message ${message.sender} ${message.error ? 'error' : ''}`}
                  >
                    <div className="chat-message-bubble">
                      {message.sender === 'ai' ? (
                        <div className="chat-message-content">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              // Custom renderers for better formatting
                              p: ({node, ...props}) => <p className="markdown-p" {...props} />,
                              ul: ({node, ...props}) => <ul className="markdown-ul" {...props} />,
                              ol: ({node, ...props}) => <ol className="markdown-ol" {...props} />,
                              li: ({node, ...props}) => <li className="markdown-li" {...props} />,
                              h1: ({node, ...props}) => <h1 className="markdown-h1" {...props} />,
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
                          {!message.error && (
                            <>
                              <button
                                className="copy-message-btn"
                                onClick={() => handleCopyMessage(message.id, message.text)}
                                aria-label="Copy message"
                                title="Copy response"
                              >
                                {copiedMessageId === message.id ? (
                                  <Check size={14} />
                                ) : (
                                  <Copy size={14} />
                                )}
                              </button>
                              <div className="feedback-buttons">
                                <button
                                  className={`feedback-btn ${message.feedback === 'positive' ? 'active' : ''}`}
                                  onClick={() => handleFeedback(message.id, 'positive')}
                                  aria-label="Helpful"
                                  title="Helpful"
                                  disabled={feedbackGiven.has(message.id)}
                                >
                                  <ThumbsUp size={14} />
                                </button>
                                <button
                                  className={`feedback-btn ${message.feedback === 'negative' ? 'active' : ''}`}
                                  onClick={() => handleFeedback(message.id, 'negative')}
                                  aria-label="Not helpful"
                                  title="Not helpful"
                                  disabled={feedbackGiven.has(message.id)}
                                >
                                  <ThumbsDown size={14} />
                                </button>
                              </div>
                            </>
                          )}
                          {message.error && (
                            <button
                              className="retry-btn"
                              onClick={() => handleRetry(message)}
                              aria-label="Retry"
                            >
                              <RotateCcw size={14} />
                              <span>Retry</span>
                            </button>
                          )}
                        </div>
                      ) : (
                        message.text
                      )}
                      <div className="message-timestamp">
                        {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Loading indicator */}
                {isLoading && (
                  <div className="chat-message ai">
                    <div className="chat-message-bubble typing" aria-label="AI is typing">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Suggested Queries - Show only in home view */}
              {showHomeView && messages.length <= 1 && !isLoading && (
                <div className="chat-agent-suggestions">
                  <h4>Popular Questions</h4>
                  <div className="suggestions-grid">
                    {SUGGESTED_QUERIES.map((query, index) => (
                      <button
                        key={index}
                        className="suggestion-chip"
                        onClick={() => handleSuggestedQuery(query)}
                        aria-label={`Ask: ${query}`}
                      >
                        {query}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Input Area */}
            <div className="chat-agent-input-area">
              <input
                ref={inputRef}
                type="text"
                className="chat-agent-input"
                placeholder="Ask a question about your assessment..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                aria-label="Type your message"
              />
              <button
                className="chat-agent-send"
                onClick={() => handleSendMessage()}
                disabled={!inputValue.trim() || isLoading}
                aria-label="Send message"
              >
                <Send size={20} />
              </button>
            </div>
          </div>
        </>
      )}
    </>
  );
};
