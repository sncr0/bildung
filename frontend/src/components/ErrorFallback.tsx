import { FallbackProps } from "react-error-boundary";

export function ErrorFallback({ error, resetErrorBoundary }: FallbackProps) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="text-center py-12">
      <h2 className="text-lg font-semibold text-stone-700 mb-2">Something went wrong</h2>
      <p className="text-stone-500 mb-4">{message}</p>
      <button
        onClick={resetErrorBoundary}
        className="px-4 py-2 bg-stone-800 text-white rounded hover:bg-stone-700"
      >
        Try again
      </button>
    </div>
  );
}
