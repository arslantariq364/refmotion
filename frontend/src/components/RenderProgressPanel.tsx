import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  Orbit,
  Play,
  Square,
} from "lucide-react";

const STAGES = [
  { key: "Validating", label: "Validating" },
  { key: "Analyzing reference", label: "Analyzing reference" },
  { key: "Analyzing source", label: "Analyzing source" },
  { key: "Creating timeline", label: "Timeline" },
  { key: "Rendering", label: "Rendering" },
  { key: "Validating output", label: "Verifying output" },
];

function getStageIndex(stageStr: string, status: string): number {
  if (status === "completed") return STAGES.length;
  const s = (stageStr || "").toLowerCase();
  if (s.includes("validating output") || s.includes("verifying")) return 5;
  if (s.includes("rendering")) return 4;
  if (s.includes("timeline") || s.includes("storyboard")) return 3;
  if (s.includes("analyzing source")) return 2;
  if (s.includes("analyzing reference")) return 1;
  return 0;
}

interface RenderProgressPanelProps {
  job: any;
  onCancel?: (jobId: string) => void;
  onOpenPreview?: () => void;
}

export function RenderProgressPanel({
  job,
  onCancel,
  onOpenPreview,
}: RenderProgressPanelProps) {
  const [elapsedSec, setElapsedSec] = useState<number>(0);

  useEffect(() => {
    if (!job) return;
    if (job.processing_duration_sec) {
      setElapsedSec(Math.round(Number(job.processing_duration_sec)));
      return;
    }
    const isRunning = job.status === "running" || job.status === "queued";
    if (!isRunning) return;

    const startMs = job.created_at ? new Date(job.created_at).getTime() : Date.now();
    const tick = () => {
      const diff = Math.max(0, Math.round((Date.now() - startMs) / 1000));
      setElapsedSec(diff);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [job]);

  if (!job) return null;

  const isRunning = job.status === "running" || job.status === "queued";
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed" || job.status === "cancelled";
  const activeIdx = getStageIndex(job.stage || "", job.status || "");

  return (
    <div
      className="rm-card p-5 max-h-[216px] flex items-center justify-between gap-6 overflow-hidden"
      aria-live="polite"
    >
      {/* Left: CSS-only 3D Cube/Rings Accent (only spins while running) */}
      <div className="flex items-center gap-5 min-w-0">
        {isRunning ? (
          <div className="rm-3d-mini-stage" aria-hidden="true">
            <div className="rm-3d-mini-ring-1" />
            <div className="rm-3d-mini-ring-2" />
            <div className="rm-3d-mini-cube">
              <div className="rm-3d-mini-face rm-3d-mini-front" />
              <div className="rm-3d-mini-face rm-3d-mini-back" />
              <div className="rm-3d-mini-face rm-3d-mini-right" />
              <div className="rm-3d-mini-face rm-3d-mini-left" />
              <div className="rm-3d-mini-face rm-3d-mini-top" />
              <div className="rm-3d-mini-face rm-3d-mini-bottom" />
            </div>
          </div>
        ) : (
          <div
            className="w-14 h-14 rounded-xl flex items-center justify-center shrink-0"
            style={{
              backgroundColor: isCompleted
                ? "var(--success-soft)"
                : isFailed
                ? "var(--danger-soft)"
                : "var(--accent-soft)",
              color: isCompleted
                ? "var(--success)"
                : isFailed
                ? "var(--danger)"
                : "var(--accent)",
            }}
          >
            {isCompleted ? (
              <CheckCircle2 className="w-7 h-7" />
            ) : isFailed ? (
              <AlertCircle className="w-7 h-7" />
            ) : (
              <Orbit className="w-7 h-7" />
            )}
          </div>
        )}

        <div className="min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <span
              className="text-[13px] font-semibold px-2 py-0.5 rounded"
              style={{
                backgroundColor: isCompleted
                  ? "var(--success-soft)"
                  : isFailed
                  ? "var(--danger-soft)"
                  : "var(--accent-soft)",
                color: isCompleted
                  ? "var(--success)"
                  : isFailed
                  ? "var(--danger)"
                  : "var(--accent)",
              }}
            >
              {job.status.toUpperCase()}
            </span>
            <span
              className="text-[13px] flex items-center gap-1"
              style={{ color: "var(--text-muted)" }}
            >
              <Clock className="w-3.5 h-3.5" />
              {elapsedSec}s elapsed • {job.rendering_engine || "ffmpeg"}
            </span>
          </div>
          <h3 className="text-[17px] font-semibold truncate">
            {job.job_type === "generate_video"
              ? "Mode B: Reference-Guided AI Video Synthesis"
              : "Mode A: Reference-Guided Raw Video Edit"}
          </h3>
          <p className="text-[13px] truncate" style={{ color: "var(--text-muted)" }}>
            Current stage: <strong style={{ color: "var(--text)" }}>{job.stage}</strong>
            {job.error_message ? ` — ${job.error_message}` : ""}
          </p>
        </div>
      </div>

      {/* Center: Compact 2-Column Vertical Stage List */}
      <div className="hidden lg:grid grid-cols-2 gap-x-6 gap-y-1.5 shrink-0">
        {STAGES.map((st, idx) => {
          const done = isCompleted || idx < activeIdx;
          const current = isRunning && idx === activeIdx;
          return (
            <div
              key={st.key}
              className="flex items-center gap-2 text-[13px]"
              style={{
                color: current
                  ? "var(--text)"
                  : done
                  ? "var(--success)"
                  : "var(--text-muted)",
                fontWeight: current ? 600 : 400,
              }}
            >
              {done ? (
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" style={{ color: "var(--success)" }} />
              ) : current ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" style={{ color: "var(--accent)" }} />
              ) : (
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: "var(--border-ui)" }}
                />
              )}
              <span>{st.label}</span>
            </div>
          );
        })}
      </div>

      {/* Right: Action Button */}
      <div className="shrink-0 flex items-center gap-2">
        {isRunning && onCancel && (
          <button
            type="button"
            onClick={() => onCancel(job.id)}
            className="rm-btn-secondary"
            style={{ color: "var(--danger)", borderColor: "var(--danger)" }}
          >
            <Square className="w-4 h-4" /> Cancel
          </button>
        )}
        {isCompleted && onOpenPreview && (
          <button
            type="button"
            onClick={onOpenPreview}
            className="rm-btn-primary"
          >
            <Play className="w-4 h-4" /> Open Monitor
          </button>
        )}
      </div>
    </div>
  );
}
