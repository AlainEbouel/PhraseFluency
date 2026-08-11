import { apiRequest } from "./client";

export interface ConversationMessage {
  id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  created_at: string;
}

export function fetchConversation(textId: string): Promise<{ messages: ConversationMessage[] }> {
  return apiRequest(`/api/v1/texts/${textId}/conversation`);
}

export function askQuestion(textId: string, question: string): Promise<ConversationMessage> {
  return apiRequest(`/api/v1/texts/${textId}/conversation/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
