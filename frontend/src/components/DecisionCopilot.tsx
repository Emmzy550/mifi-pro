import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Bot, Loader2, Send, Sparkles, X } from 'lucide-react';
import { api, useAuth } from '../context/AuthContext';

type CopilotRole = 'user' | 'assistant' | 'system';
type CopilotMode =
  | 'decision_mode'
  | 'intake_mode'
  | 'policy_mode'
  | 'audit_mode'
  | 'settings_mode'
  | 'console_mode';

type CopilotMessage = {
  id: string;
  role: CopilotRole;
  content: string;
  createdAt: number;
};

type DecisionContextMeta = {
  decisionId: string;
  policyVersion: string;
  status: string;
};

type AssistantResponseMeta = {
  provider: string;
  model: string;
  requestId: string;
  mode: CopilotMode;
};

type AssistantChatResponse = {
  reply?: string;
  meta?: AssistantResponseMeta;
};

type AssistantBlock =
  | { type: 'paragraph'; text: string }
  | { type: 'label'; text: string }
  | { type: 'bullets'; items: string[] };

type DecisionCopilotProps = {
  onDockedOpenChange?: (isDockedOpen: boolean) => void;
};

const createMessage = (role: CopilotRole, content: string): CopilotMessage => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role,
  content,
  createdAt: Date.now()
});

const formatTime = (value: number) =>
  new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

const getMode = (pathname: string): CopilotMode => {
  if (pathname.startsWith('/decisions')) return 'decision_mode';
  if (pathname.startsWith('/manual-assessments')) return 'intake_mode';
  if (pathname.startsWith('/policy-studio')) return 'policy_mode';
  if (pathname.startsWith('/audit-logs')) return 'audit_mode';
  if (pathname.startsWith('/settings')) return 'settings_mode';
  return 'console_mode';
};

const getSuggestions = (mode: CopilotMode, hasDecisionContext: boolean) => {
  if (mode === 'decision_mode' && hasDecisionContext) {
    return ['Explain recommendation', 'Which rules fired?', 'What if amount changes?'];
  }

  if (mode === 'decision_mode') {
    return [
      'How do I explain decision outcomes?',
      'What does risk score mean?',
      'How do I compare policy versions?'
    ];
  }

  if (mode === 'intake_mode') {
    return ['Batch uploads', 'File format', 'Validation checks'];
  }

  if (mode === 'policy_mode') {
    return [
      'How do rule priorities work?',
      'Which thresholds control affordability?',
      'How should I document overrides?'
    ];
  }

  if (mode === 'audit_mode') {
    return [
      'What does FINAL_HUMAN_DECISION_SEALED mean?',
      'How do I trace who changed this decision?',
      'What should I investigate first?'
    ];
  }

  if (mode === 'settings_mode') {
    return [
      'Which settings are safe to change?',
      'How do role changes affect approvals?',
      'Where do I verify config updates?'
    ];
  }

  return [
    'What can you help me with?',
    'How do I interpret risk levels?',
    'Where can I review policy rules?'
  ];
};

const parseAssistantBlocks = (content: string): AssistantBlock[] => {
  const lines = content
    .replace(/\*\*/g, '')
    .split('\n')
    .map((line) => line.trim());

  const blocks: AssistantBlock[] = [];
  let paragraphBuffer: string[] = [];
  let bulletBuffer: string[] = [];

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) return;
    blocks.push({ type: 'paragraph', text: paragraphBuffer.join(' ').trim() });
    paragraphBuffer = [];
  };

  const flushBullets = () => {
    if (bulletBuffer.length === 0) return;
    blocks.push({ type: 'bullets', items: [...bulletBuffer] });
    bulletBuffer = [];
  };

  lines.forEach((line) => {
    if (!line) {
      flushParagraph();
      flushBullets();
      return;
    }

    if (/^[-•*]\s+/.test(line)) {
      flushParagraph();
      bulletBuffer.push(line.replace(/^[-•*]\s+/, '').trim());
      return;
    }

    if (line.endsWith(':') && line.length < 40) {
      flushParagraph();
      flushBullets();
      blocks.push({ type: 'label', text: line.replace(/:$/, '') });
      return;
    }

    if (bulletBuffer.length > 0) {
      flushBullets();
    }
    paragraphBuffer.push(line);
  });

  flushParagraph();
  flushBullets();
  return blocks;
};

const AssistantBubbleContent = ({ content }: { content: string }) => {
  const blocks = parseAssistantBlocks(content);

  return (
    <div className="copilot-structured-content">
      {blocks.map((block, blockIndex) => (
        <React.Fragment key={`assistant-block-${blockIndex}`}>
          {block.type === 'paragraph' && (
            <p className="copilot-message-content">{block.text}</p>
          )}
          {block.type === 'label' && (
            <p className="copilot-structured-title">{block.text}</p>
          )}
          {block.type === 'bullets' && (
            <ul className="copilot-structured-list">
              {block.items.map((item, itemIndex) => (
                <li key={`assistant-bullet-${blockIndex}-${itemIndex}`}>{item}</li>
              ))}
            </ul>
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

export default function DecisionCopilot({ onDockedOpenChange }: DecisionCopilotProps) {
  const location = useLocation();
  const { user } = useAuth();

  const [isOpen, setIsOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(min-width: 1280px)').matches;
  });
  const [isSending, setIsSending] = useState(false);
  const [draft, setDraft] = useState('');
  const [decisionMeta, setDecisionMeta] = useState<DecisionContextMeta | null>(null);
  const [isDecisionContextLoading, setIsDecisionContextLoading] = useState(false);
  const [lastResponseMeta, setLastResponseMeta] = useState<AssistantResponseMeta | null>(null);
  const [conversations, setConversations] = useState<Record<string, CopilotMessage[]>>({});
  const [unreadByContext, setUnreadByContext] = useState<Record<string, boolean>>({});

  const threadRef = useRef<HTMLDivElement | null>(null);
  const decisionMatch = location.pathname.match(/^\/decisions\/([^/]+)$/);
  const decisionId = decisionMatch?.[1];
  const contextMode = getMode(location.pathname);
  const contextKey = decisionId ? `decision:${decisionId}` : `route:${location.pathname}`;
  const messages = conversations[contextKey] || [];
  const hasUnread = Object.values(unreadByContext).some(Boolean);
  const isComposerExpanded = draft.includes('\n') || draft.length > 100;
  const isDockedOpen = isOpen && isDesktop;
  const showDevProviderMeta = import.meta.env.DEV;
  const suggestions = useMemo(
    () => getSuggestions(contextMode, Boolean(decisionId)),
    [contextMode, decisionId]
  );

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1280px)');
    const handleMediaChange = () => setIsDesktop(media.matches);
    handleMediaChange();

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', handleMediaChange);
      return () => media.removeEventListener('change', handleMediaChange);
    }

    media.addListener(handleMediaChange);
    return () => media.removeListener(handleMediaChange);
  }, []);

  useEffect(() => {
    onDockedOpenChange?.(isDockedOpen);
  }, [isDockedOpen, onDockedOpenChange]);

  useEffect(() => {
    let cancelled = false;

    if (!decisionId) {
      setDecisionMeta(null);
      return () => {
        cancelled = true;
      };
    }

    setIsDecisionContextLoading(true);
    api
      .get(`/assessment/${decisionId}`)
      .then((res) => {
        if (cancelled) return;
        const record = res.data || {};
        const status = record?.final_decision_metadata ? 'SEALED' : 'PENDING_OFFICER';
        setDecisionMeta({
          decisionId,
          policyVersion: record?.policy_version || 'Unavailable',
          status
        });
      })
      .catch(() => {
        if (cancelled) return;
        setDecisionMeta({
          decisionId,
          policyVersion: 'Unavailable',
          status: 'Unavailable'
        });
      })
      .finally(() => {
        if (!cancelled) setIsDecisionContextLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [decisionId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isTypingTarget =
        !!target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable);

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        if (isTypingTarget) return;
        event.preventDefault();
        setIsOpen((prev) => !prev);
      }

      if (event.key === 'Escape' && isOpen && !isDesktop) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isDesktop, isOpen]);

  useEffect(() => {
    if (isOpen) {
      setUnreadByContext((prev) => ({ ...prev, [contextKey]: false }));
    }
  }, [isOpen, contextKey]);

  useEffect(() => {
    if (!threadRef.current) return;
    threadRef.current.scrollTop = threadRef.current.scrollHeight;
  }, [messages, isSending, isOpen]);

  const appendMessage = (key: string, message: CopilotMessage) => {
    setConversations((prev) => ({
      ...prev,
      [key]: [...(prev[key] || []), message]
    }));
  };

  const sendMessage = async (seed?: string) => {
    const text = (seed ?? draft).trim();
    if (!text || isSending) return;

    const userMessage = createMessage('user', text);
    const thread = [...messages, userMessage];
    setConversations((prev) => ({ ...prev, [contextKey]: thread }));
    setDraft('');
    setIsSending(true);

    try {
      const messagesForPayload = thread
        .slice(-40)
        .map((item) => ({ role: item.role, content: item.content }));

      const response = await api.post<AssistantChatResponse>('/assistant/chat', {
        messages: messagesForPayload,
        context: {
          route: location.pathname,
          decisionId: decisionMeta?.decisionId || decisionId,
          policyVersion: decisionMeta?.policyVersion,
          status: decisionMeta?.status,
          orgId: user?.organization_id,
          userRole: user?.role
        }
      });

      const replyText =
        `${response?.data?.reply || ''}`.trim() ||
        'I do not have enough verified context to answer that request.';
      if (response?.data?.meta) {
        setLastResponseMeta(response.data.meta);
      }
      appendMessage(contextKey, createMessage('assistant', replyText));

      if (!isOpen) {
        setUnreadByContext((prev) => ({ ...prev, [contextKey]: true }));
      }
    } catch {
      appendMessage(
        contextKey,
        createMessage(
          'assistant',
          'I could not complete that request right now. Please retry in a few seconds.'
        )
      );
      setLastResponseMeta((prev) => prev ?? null);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="copilot-root" aria-live="polite">
      {isOpen && !isDesktop && (
        <button
          type="button"
          aria-label="Close Decision Copilot"
          className="copilot-backdrop"
          onClick={() => setIsOpen(false)}
        />
      )}

      <aside
        className={`copilot-panel ${
          isDesktop ? 'copilot-panel-docked' : 'copilot-panel-overlay'
        } ${isOpen ? 'copilot-panel-open' : 'copilot-panel-closed'}`}
        role="dialog"
        aria-modal={!isDesktop && isOpen}
        aria-label="Decision Copilot"
      >
        <header className="copilot-header">
          <div>
            <p className="copilot-title">Decision Copilot</p>
            <p className="copilot-subtitle">
              Ask about this assessment, policy rules, or workflow.
            </p>
          </div>
          <button
            type="button"
            className="copilot-close-btn"
            onClick={() => setIsOpen(false)}
            aria-label="Close assistant panel"
          >
            <X size={16} />
          </button>
        </header>

        <div className="copilot-pills">
          {decisionId ? (
            <>
              <span className="copilot-pill">Decision: {decisionId}</span>
              <span className="copilot-pill">
                Policy:{' '}
                {isDecisionContextLoading ? 'Loading...' : decisionMeta?.policyVersion || 'Unavailable'}
              </span>
              <span className="copilot-pill">
                Status: {isDecisionContextLoading ? 'Loading...' : decisionMeta?.status || 'Unavailable'}
              </span>
            </>
          ) : (
            <span className="copilot-pill">Context: Partner Console</span>
          )}
        </div>

        <div className="copilot-suggestions">
          {suggestions.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="copilot-suggestion-chip"
              onClick={() => void sendMessage(prompt)}
              disabled={isSending}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div ref={threadRef} className="copilot-thread">
          {messages.length === 0 ? (
            <div className="copilot-empty-state">
              <Sparkles size={16} />
              <p>Start with a suggested prompt or ask a decision question.</p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`copilot-message ${
                  message.role === 'user' ? 'copilot-message-user' : 'copilot-message-assistant'
                }`}
              >
                {message.role !== 'user' && (
                  <div className="copilot-message-avatar" aria-hidden>
                    <Bot size={14} />
                  </div>
                )}
                <div className="copilot-bubble">
                  {message.role === 'assistant' ? (
                    <AssistantBubbleContent content={message.content} />
                  ) : (
                    <p className="copilot-message-content">{message.content}</p>
                  )}
                  <time className="copilot-time">{formatTime(message.createdAt)}</time>
                </div>
              </div>
            ))
          )}

          {isSending && (
            <div className="copilot-message copilot-message-assistant">
              <div className="copilot-message-avatar" aria-hidden>
                <Bot size={14} />
              </div>
              <div className="copilot-bubble">
                <div className="copilot-typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="copilot-composer">
          <textarea
            aria-label="Message Decision Copilot"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                void sendMessage();
              }
            }}
            rows={isComposerExpanded ? 3 : 1}
            className="copilot-input"
            placeholder="Ask a question..."
          />
          <button
            type="button"
            className="copilot-send-btn"
            onClick={() => void sendMessage()}
            disabled={isSending || !draft.trim()}
            aria-label="Send message"
          >
            {isSending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>

        {showDevProviderMeta && (
          <div className="copilot-dev-footer" aria-live="polite">
            Provider: {lastResponseMeta?.provider || 'n/a'} • Model: {lastResponseMeta?.model || 'n/a'} • Req: {lastResponseMeta?.requestId || 'n/a'}
          </div>
        )}
      </aside>

      {!isDockedOpen && (
        <button
          type="button"
          title="Decision Copilot"
          aria-label="Open Decision Copilot"
          className="copilot-fab"
          onClick={() => setIsOpen(true)}
        >
          <Bot size={18} />
          <span className="copilot-fab-label">Decision Copilot</span>
          {hasUnread && <span className="copilot-unread-dot" aria-hidden />}
        </button>
      )}
    </div>
  );
}
