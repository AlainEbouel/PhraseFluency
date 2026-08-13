import { useRef, useState } from "react";
import { Volume2 } from "lucide-react";

export function AudioButton({ src, label }: { src: string; label: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasError, setHasError] = useState(false);

  function handleClick() {
    setHasError(false);
    audioRef.current?.play().catch(() => setHasError(true));
  }

  return (
    <span className="audio-button">
      <button
        type="button"
        className="audio-button-control"
        onClick={handleClick}
        aria-label={`Écouter : ${label}`}
        disabled={isPlaying}
      >
        <Volume2 />
      </button>
      <audio
        ref={audioRef}
        src={src}
        preload="none"
        onPlay={() => setIsPlaying(true)}
        onEnded={() => setIsPlaying(false)}
        onError={() => {
          setIsPlaying(false);
          setHasError(true);
        }}
      />
      {hasError && <span className="audio-button-error">Audio indisponible</span>}
    </span>
  );
}
