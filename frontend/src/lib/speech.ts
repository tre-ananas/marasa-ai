/**
 * Thin wrapper over the browser's Web Speech API.
 *
 * Chrome and Edge support speech recognition; Firefox and Safari do not
 * (Safari has a limited `webkitSpeechRecognition`). When recognition is
 * unavailable the app falls back to text input and says so plainly.
 */

export interface RecognitionResultEvent extends Event {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: { isFinal: boolean; 0: { transcript: string } };
  };
}

export interface RecognitionErrorEvent extends Event {
  error?: string;
}

export interface RecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: RecognitionResultEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

type RecognitionConstructor = new () => RecognitionLike;

function constructor(): RecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const scope = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

export function isSpeechSupported(): boolean {
  return constructor() !== null;
}

export interface RecognizerHandlers {
  onPartial?: (transcript: string) => void;
  onFinal?: (transcript: string) => void;
  onError?: (message: string) => void;
  onEnd?: () => void;
}

export function createRecognizer(locale: string, handlers: RecognizerHandlers): RecognitionLike | null {
  const Recognition = constructor();
  if (!Recognition) return null;

  const recognition = new Recognition();
  recognition.lang = locale || "en-US";
  recognition.continuous = false;
  recognition.interimResults = true;

  let finalText = "";

  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const result = event.results[index];
      const transcript = result[0].transcript;
      if (result.isFinal) {
        finalText += transcript;
      } else {
        interim += transcript;
      }
    }
    if (interim) handlers.onPartial?.(interim);
    if (finalText) handlers.onFinal?.(finalText.trim());
  };

  recognition.onerror = (event) => {
    const code = event.error ?? "unknown";
    const message =
      code === "not-allowed"
        ? "Microphone access was denied. Allow it in your browser, or type instead."
        : `Speech recognition failed (${code}).`;
    handlers.onError?.(message);
  };

  recognition.onend = () => handlers.onEnd?.();

  return recognition;
}
