import { useCallback, useRef, useState } from "react";

export function useAudioRecorder(onRecorded: (blob: Blob) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        window.isSecureContext
          ? "Le microphone n'est pas pris en charge par ce navigateur."
          : "Le microphone nécessite une connexion sécurisée (HTTPS). Utilisez le clavier sur cette adresse."
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        onRecorded(blob);
      };
      recorder.start();
      recorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      setError("Microphone indisponible ou permission refusée.");
    }
  }, [onRecorded]);

  const stop = useCallback(() => {
    recorderRef.current?.stop();
    setIsRecording(false);
  }, []);

  return { isRecording, error, start, stop };
}
