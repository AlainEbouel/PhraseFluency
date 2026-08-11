import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { askQuestion, fetchConversation } from "../../api/conversations";
import type { ConversationMessage } from "../../api/conversations";

export function ChatPanel({ textId }: { textId: string }) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConversation(textId)
      .then((res) => setMessages(res.messages))
      .catch(() => setError("Impossible de charger la conversation."));
  }, [textId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim()) return;
    setIsSending(true);
    setError(null);
    const asked = question;
    setMessages((prev) => [
      ...prev,
      { id: `pending-${Date.now()}`, role: "USER", content: asked, created_at: new Date(0).toISOString() },
    ]);
    setQuestion("");
    try {
      const reply = await askQuestion(textId, asked);
      setMessages((prev) => [...prev, reply]);
    } catch {
      setError("La réponse a échoué. Réessayez.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <div className="chat-panel">
      <h3>Poser une question à l'IA</h3>
      <div className="chat-messages">
        {messages.map((message) => (
          <div key={message.id} className={`chat-message chat-message-${message.role.toLowerCase()}`}>
            {message.content}
          </div>
        ))}
      </div>
      {error && <p className="error-text">{error}</p>}
      <form onSubmit={handleSubmit} className="chat-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Pourquoi cette formulation ? Une autre façon de le dire ?"
          disabled={isSending}
        />
        <button type="submit" disabled={isSending || !question.trim()}>
          {isSending ? "..." : "Envoyer"}
        </button>
      </form>
    </div>
  );
}
