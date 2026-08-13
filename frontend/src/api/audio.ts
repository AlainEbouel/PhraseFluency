const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export function preferredAudioUrl(textId: string): string {
  return `${API_BASE_URL}/api/v1/audio/reference/${textId}/preferred`;
}

export function alternativeAudioUrl(textId: string, index: number): string {
  return `${API_BASE_URL}/api/v1/audio/reference/${textId}/alternative/${index}`;
}
