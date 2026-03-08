import React, { useState, useCallback } from 'react';
import './CodePane.css';

export interface CodePaneProps {
  code: string;
  language?: string;
  title?: string;
  className?: string;
  maxHeight?: string;
  showLineNumbers?: boolean;
  wrap?: boolean;
}

export const CodePane: React.FC<CodePaneProps> = ({
  code,
  language,
  title,
  className = '',
  maxHeight,
  showLineNumbers = false,
  wrap = false,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = code;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [code]);

  const lines = code ? code.split('\n') : [];
  const hasHeader = Boolean(title) || code.length > 0;

  const contentClass = [
    'code-pane__line-content',
    !showLineNumbers ? 'code-pane__line-content--no-border' : '',
    wrap ? 'code-pane__line-content--wrap' : 'code-pane__line-content--nowrap',
  ].filter(Boolean).join(' ');

  return (
    <div
      className={`code-pane ${className}`}
      role="region"
      aria-label={title || 'Code display'}
    >
      {(title || code.length > 0) && (
        <div className="code-pane__header">
          <span className="code-pane__title">
            {title}
            {language && title && (
              <> &middot; {language}</>
            )}
            {language && !title && language}
          </span>
          <div className="code-pane__actions">
            <button
              className={`code-pane__copy-btn ${copied ? 'code-pane__copy-btn--copied' : ''}`}
              onClick={handleCopy}
              title={copied ? 'Copied!' : 'Copy to clipboard'}
              aria-label={copied ? 'Copied to clipboard' : 'Copy code to clipboard'}
              type="button"
            >
              {copied ? (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <path d="M3 8.5l3 3 7-7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
                  <rect x="5.5" y="5.5" width="7" height="7" rx="1" />
                  <path d="M10.5 5.5V4a1 1 0 00-1-1H4a1 1 0 00-1 1v5.5a1 1 0 001 1h1.5" />
                </svg>
              )}
            </button>
          </div>
        </div>
      )}

      <div
        className={`code-pane__body ${!hasHeader ? 'code-pane__body--no-header' : ''}`}
        style={maxHeight ? { maxHeight, overflow: 'auto' } : undefined}
      >
        {lines.length === 0 ? (
          <div className="code-pane__empty">No code to display</div>
        ) : (
          <table className="code-pane__table">
            <tbody>
              {lines.map((line, index) => (
                <tr key={index}>
                  {showLineNumbers && (
                    <td className="code-pane__line-number" aria-hidden="true">
                      {index + 1}
                    </td>
                  )}
                  <td className={contentClass}>{line || '\u00A0'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
