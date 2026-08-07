interface ProgressBarProps {
  progress: number;
  status: string;
  message: string | null;
}

export function ProgressBar({ progress, status, message }: ProgressBarProps) {
  if (status === "ready") {
    return (
      <div className="progress-bar ready" role="status">
        <span>✅ Indexado · {message}</span>
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="progress-bar failed" role="alert">
        <span>❌ Error: {message ?? "indexación fallida"}</span>
      </div>
    );
  }
  return (
    <div className="progress-bar" role="progressbar" aria-valuenow={progress}>
      <div className="progress-fill" style={{ width: `${progress}%` }} />
      <span>
        {status} · {Math.round(progress)}% · {message ?? ""}
      </span>
    </div>
  );
}
