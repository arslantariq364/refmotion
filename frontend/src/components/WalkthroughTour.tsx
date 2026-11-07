import React, { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Compass, X } from "lucide-react";

export interface TourStep {
  selector: string;
  title: string;
  description: string;
}

const TOUR_STEPS: TourStep[] = [
  {
    selector: '[data-tour="sidebar"]',
    title: "Studio Navigation Sidebar",
    description:
      "Switch between Create workflows (Generate, Edit), your Reference Vault & Projects, and System tools. Collapse to icon-only mode anytime.",
  },
  {
    selector: '[data-tour="generate-card"]',
    title: "Generate New Video (Mode B)",
    description:
      "Create original videos from a topic or script. Uses 70% reference script/voice cadence and a 60/40 visual blend from your Reference Vault.",
  },
  {
    selector: '[data-tour="edit-card"]',
    title: "Edit My Video (Mode A)",
    description:
      "Upload raw footage and attach a reference clip. Blends 50% of your attached reference style with 50% of your stored category vault.",
  },
  {
    selector: '[data-tour="nav-library"]',
    title: "Reference Vault",
    description:
      "Browse, search, preview, and organize reference videos by category folder with scene pacing and color telemetry.",
  },
  {
    selector: '[data-tour="nav-queue"]',
    title: "Render Queue & Live Progress",
    description:
      "Monitor active renders with real-time pipeline stages, elapsed time, and instant cancellation.",
  },
  {
    selector: '[data-tour="help-menu"]',
    title: "Help & Walkthrough Menu",
    description:
      "Replay this guided tour or reopen the First-Run Setup Wizard anytime from the top bar.",
  },
];

interface WalkthroughTourProps {
  isOpen: boolean;
  onClose: () => void;
  onEnsureDashboard: () => void;
}

export function WalkthroughTour({
  isOpen,
  onClose,
  onEnsureDashboard,
}: WalkthroughTourProps) {
  const [stepIdx, setStepIdx] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setStepIdx(0);
    onEnsureDashboard();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const updatePosition = () => {
      const step = TOUR_STEPS[stepIdx];
      if (!step) return;
      const el = document.querySelector(step.selector) as HTMLElement | null;
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setRect(el.getBoundingClientRect());
      } else {
        setRect(null);
      }
    };
    const timer = setTimeout(updatePosition, 60);
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [isOpen, stepIdx]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        finishTour();
      } else if (e.key === "ArrowRight") {
        if (stepIdx < TOUR_STEPS.length - 1) setStepIdx((i) => i + 1);
        else finishTour();
      } else if (e.key === "ArrowLeft") {
        if (stepIdx > 0) setStepIdx((i) => i - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, stepIdx]);

  const finishTour = () => {
    try {
      localStorage.setItem("refmotion_tour_done", "true");
    } catch {
      // ignore storage errors
    }
    onClose();
  };

  if (!isOpen) return null;

  const current = TOUR_STEPS[stepIdx];
  const pad = 6;

  // Compute anchored tooltip coordinates within viewport bounds
  let tooltipTop = 120;
  let tooltipLeft = Math.max(16, window.innerWidth / 2 - 180);
  if (rect) {
    const spaceBelow = window.innerHeight - rect.bottom;
    if (spaceBelow > 210) {
      tooltipTop = rect.bottom + 14;
    } else if (rect.top > 210) {
      tooltipTop = Math.max(16, rect.top - 195);
    } else {
      tooltipTop = Math.max(16, rect.top + 16);
    }
    tooltipLeft = Math.min(
      window.innerWidth - 360,
      Math.max(16, rect.left)
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 pointer-events-auto"
      role="dialog"
      aria-modal="true"
      aria-label={`Guided walkthrough step ${stepIdx + 1} of ${TOUR_STEPS.length}`}
    >
      {/* Dimmed Backdrop with Spotlight Cutout */}
      <div
        onClick={finishTour}
        className="fixed inset-0 transition-opacity"
        style={{ backgroundColor: "rgba(11, 15, 26, 0.55)" }}
      />

      {rect && (
        <div
          className="fixed pointer-events-none rounded-xl transition-all duration-150"
          style={{
            top: rect.top - pad,
            left: rect.left - pad,
            width: rect.width + pad * 2,
            height: rect.height + pad * 2,
            border: "2px solid var(--accent)",
            boxShadow: "0 0 0 9999px rgba(11, 15, 26, 0.62)",
            zIndex: 51,
          }}
        />
      )}

      {/* Coachmark Tooltip Card */}
      <div
        className="rm-card fixed p-5 w-[340px] space-y-3"
        style={{
          top: tooltipTop,
          left: tooltipLeft,
          zIndex: 52,
          borderColor: "var(--accent)",
        }}
      >
        <div className="flex items-center justify-between">
          <span
            className="text-[13px] font-semibold flex items-center gap-1.5"
            style={{ color: "var(--accent)" }}
          >
            <Compass className="w-4 h-4" />
            Step {stepIdx + 1} of {TOUR_STEPS.length}
          </span>
          <button
            type="button"
            onClick={finishTour}
            className="rm-btn-ghost p-1 min-h-0"
            aria-label="Close walkthrough tour"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>
          <h4 className="text-[16px] font-semibold">{current.title}</h4>
          <p className="text-[14px] mt-1" style={{ color: "var(--text-muted)" }}>
            {current.description}
          </p>
        </div>

        <div className="flex items-center justify-between pt-2 border-t">
          <button
            type="button"
            onClick={finishTour}
            className="rm-btn-ghost text-[13px]"
          >
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {stepIdx > 0 && (
              <button
                type="button"
                onClick={() => setStepIdx((i) => i - 1)}
                className="rm-btn-secondary px-3 min-h-[36px] text-[13px]"
              >
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
            )}
            {stepIdx < TOUR_STEPS.length - 1 ? (
              <button
                type="button"
                onClick={() => setStepIdx((i) => i + 1)}
                className="rm-btn-primary px-3.5 min-h-[36px] text-[13px]"
              >
                Next <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={finishTour}
                className="rm-btn-primary px-4 min-h-[36px] text-[13px]"
              >
                Finish
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
