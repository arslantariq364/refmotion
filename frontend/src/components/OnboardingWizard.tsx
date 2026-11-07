import React, { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Film,
  FolderPlus,
  Loader2,
  Orbit,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { api } from "../api";

interface OnboardingFileItem {
  id: string;
  file: File;
  category: string;
  stage:
    | "queued"
    | "uploading"
    | "validating"
    | "analyzing"
    | "indexed"
    | "error";
  uploadPct: number;
  stageLabel: string;
  errorMsg?: string;
  asset?: any;
}

interface OnboardingWizardProps {
  isOpen: boolean;
  capabilities: any;
  categories: string[];
  categoryCounts: Record<string, number>;
  onClose: (startTour: boolean) => void;
  onRefreshData: () => Promise<void>;
}

export function OnboardingWizard({
  isOpen,
  capabilities,
  categories,
  categoryCounts,
  onClose,
  onRefreshData,
}: OnboardingWizardProps) {
  const [step, setStep] = useState<number>(1);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([
    "animals",
    "nature",
    "business",
  ]);
  const [newCategoryName, setNewCategoryName] = useState("");
  const [catError, setCatError] = useState("");
  const [addingCat, setAddingCat] = useState(false);
  const [fileItems, setFileItems] = useState<OnboardingFileItem[]>([]);
  const [submittingFinish, setSubmittingFinish] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        handleComplete(false);
      } else if (e.key === "Tab" && modalRef.current) {
        const focusables = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  if (!isOpen) return null;

  const ffmpegOk = Boolean(capabilities?.tools?.ffmpeg?.installed);
  const ffprobeOk = Boolean(capabilities?.tools?.ffprobe?.installed);
  const ttsOk = Boolean(
    capabilities?.providers?.text_to_speech?.kokoro_onnx_available ||
      capabilities?.providers?.text_to_speech?.piper_onnx_available ||
      capabilities?.providers?.text_to_speech?.espeak_available
  );

  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    const raw = newCategoryName.trim().toLowerCase();
    if (!raw) return;
    if (!/^[a-z0-9_-]{2,32}$/.test(raw)) {
      setCatError("Use 2-32 lowercase letters, numbers, hyphens, or underscores.");
      return;
    }
    setCatError("");
    setAddingCat(true);
    try {
      const res = await api.createCategory(raw);
      const created = res.category || raw;
      if (!selectedCategories.includes(created)) {
        setSelectedCategories((prev) => [...prev, created]);
      }
      setNewCategoryName("");
      await onRefreshData();
    } catch (err: any) {
      setCatError(err.message || "Could not create category");
    } finally {
      setAddingCat(false);
    }
  };

  const ingestSingleItem = async (item: OnboardingFileItem) => {
    setFileItems((prev) =>
      prev.map((f) =>
        f.id === item.id
          ? {
              ...f,
              stage: "uploading",
              uploadPct: 0,
              stageLabel: "Uploading stream...",
              errorMsg: undefined,
            }
          : f
      )
    );

    const fd = new FormData();
    fd.append("file", item.file);
    fd.append("category", item.category);
    fd.append(
      "title",
      item.file.name.replace(/\.[^/.]+$/, "").replace(/[_-]+/g, " ")
    );
    fd.append("tags", `${item.category},onboarding,reference`);
    fd.append("license_info", "User Confirmed Licensed / Own Content");

    try {
      const asset = await api.ingestReferenceWithProgress(fd, (pct) => {
        setFileItems((prev) =>
          prev.map((f) => {
            if (f.id !== item.id) return f;
            if (pct < 100) {
              return {
                ...f,
                stage: "uploading",
                uploadPct: pct,
                stageLabel: `Uploading (${pct}%)`,
              };
            }
            return {
              ...f,
              stage: "analyzing",
              uploadPct: 100,
              stageLabel:
                "Validating, fingerprinting, detecting scenes & indexing style profile...",
            };
          })
        );
      });

      setFileItems((prev) =>
        prev.map((f) =>
          f.id === item.id
            ? {
                ...f,
                stage: "indexed",
                uploadPct: 100,
                stageLabel: `Indexed in ${asset.category} (${Number(
                  asset.duration || 0
                ).toFixed(1)}s)`,
                asset,
              }
            : f
        )
      );
      await onRefreshData();
    } catch (err: any) {
      setFileItems((prev) =>
        prev.map((f) =>
          f.id === item.id
            ? {
                ...f,
                stage: "error",
                stageLabel: "Ingestion failed",
                errorMsg: err.message || "Invalid or duplicate video file",
              }
            : f
        )
      );
    }
  };

  const handleFilesSelected = (category: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    const newItems: OnboardingFileItem[] = Array.from(files).map((file) => ({
      id: `${category}-${file.name}-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 6)}`,
      file,
      category,
      stage: "queued",
      uploadPct: 0,
      stageLabel: "Queued for ingestion",
    }));
    setFileItems((prev) => [...prev, ...newItems]);
    newItems.forEach((item) => {
      ingestSingleItem(item);
    });
  };

  const handleComplete = async (startTour: boolean) => {
    setSubmittingFinish(true);
    try {
      await api.updateOnboarding(true);
      await onRefreshData();
    } catch {
      // Allow closing even if offline
    } finally {
      setSubmittingFinish(false);
      onClose(startTour);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(11, 15, 26, 0.82)", backdropFilter: "blur(6px)" }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      <div
        ref={modalRef}
        className="rm-card w-full max-w-3xl overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Top Modal Header & 4-Step Progress Bar */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{ backgroundColor: "var(--surface-2)" }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: "var(--accent-soft)", color: "var(--accent)" }}
            >
              <Orbit className="w-5 h-5" />
            </div>
            <div>
              <h2 id="onboarding-title" className="text-[18px] font-semibold">
                RefMotion Studio Setup
              </h2>
              <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                Step {step} of 4 — First-Run Configuration
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {[1, 2, 3, 4].map((s) => (
              <div
                key={s}
                className="h-2 w-8 rounded-full transition-colors"
                style={{
                  backgroundColor:
                    s <= step ? "var(--accent)" : "var(--border-ui)",
                }}
              />
            ))}
            <button
              type="button"
              onClick={() => handleComplete(false)}
              className="rm-btn-ghost ml-2"
              aria-label="Skip onboarding setup"
            >
              Skip
            </button>
          </div>
        </div>

        {/* Step Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <h3 className="text-[20px] font-semibold">
                  Welcome to RefMotion
                </h3>
                <p className="mt-1" style={{ color: "var(--text-muted)" }}>
                  Your local reference-driven AI video editing and generation studio.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px] flex items-center gap-2">
                    <Sparkles className="w-4 h-4" style={{ color: "var(--accent)" }} />
                    1. Reference-Guided AI
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Generate new videos inheriting 70% script/voice cadence and a 60/40 visual blend from your reference vault.
                  </p>
                </div>
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px] flex items-center gap-2">
                    <Film className="w-4 h-4" style={{ color: "var(--accent-2)" }} />
                    2. 50/50 Hybrid Editing
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Edit raw footage combining 50% of your attached reference clip with 50% of your stored category library.
                  </p>
                </div>
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px] flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4" style={{ color: "var(--success)" }} />
                    3. 100% Local & Private
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Runs locally on your hardware. Only explicit Reference Vault uploads are stored for reuse, and must be licensed or your own content.
                  </p>
                </div>
              </div>

              {/* System Capability Check */}
              <div className="rm-card p-4 space-y-3">
                <div className="font-semibold text-[15px]">
                  Detected System Capabilities
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="rm-card-subtle p-3 flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium text-[14px]">FFmpeg Renderer</div>
                      <div className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                        {ffmpegOk
                          ? "Installed & verified"
                          : "Missing — install via: sudo apt install ffmpeg"}
                      </div>
                    </div>
                    {ffmpegOk ? (
                      <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: "var(--success)" }} />
                    ) : (
                      <AlertCircle className="w-5 h-5 shrink-0" style={{ color: "var(--danger)" }} />
                    )}
                  </div>

                  <div className="rm-card-subtle p-3 flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium text-[14px]">FFprobe Inspector</div>
                      <div className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                        {ffprobeOk
                          ? "Stream validator ready"
                          : "Missing — install via: sudo apt install ffmpeg"}
                      </div>
                    </div>
                    {ffprobeOk ? (
                      <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: "var(--success)" }} />
                    ) : (
                      <AlertCircle className="w-5 h-5 shrink-0" style={{ color: "var(--danger)" }} />
                    )}
                  </div>

                  <div className="rm-card-subtle p-3 flex items-start justify-between gap-2">
                    <div>
                      <div className="font-medium text-[14px]">Neural Voice Models</div>
                      <div className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                        {ttsOk
                          ? `Active (${capabilities?.providers?.text_to_speech?.active_provider || "kokoro_onnx"})`
                          : "Missing — place ONNX voice models in storage/models/voices"}
                      </div>
                    </div>
                    {ttsOk ? (
                      <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: "var(--success)" }} />
                    ) : (
                      <AlertCircle className="w-5 h-5 shrink-0" style={{ color: "var(--warning)" }} />
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <div>
                <h3 className="text-[20px] font-semibold">
                  Choose Your Reference Categories
                </h3>
                <p className="mt-1" style={{ color: "var(--text-muted)" }}>
                  Select the categories you work with most, or add a custom category folder.
                </p>
              </div>

              <div className="flex flex-wrap gap-2.5">
                {categories.map((cat) => {
                  const active = selectedCategories.includes(cat);
                  const count = categoryCounts[cat] || 0;
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => toggleCategory(cat)}
                      className="px-3.5 py-2 rounded-lg text-[14px] font-medium border flex items-center gap-2 transition"
                      style={{
                        backgroundColor: active ? "var(--accent-soft)" : "var(--surface-2)",
                        borderColor: active ? "var(--accent)" : "var(--border-ui)",
                        color: "var(--text)",
                      }}
                    >
                      <span className="capitalize">{cat}</span>
                      <span
                        className="px-1.5 py-0.5 rounded text-[13px]"
                        style={{
                          backgroundColor: "var(--surface)",
                          color: "var(--text-muted)",
                        }}
                      >
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>

              <form onSubmit={handleAddCategory} className="rm-card-subtle p-4 space-y-2">
                <label
                  htmlFor="new-cat-input"
                  className="block text-[14px] font-medium"
                >
                  Add a New Category
                </label>
                <div className="flex gap-2">
                  <input
                    id="new-cat-input"
                    type="text"
                    value={newCategoryName}
                    onChange={(e) => setNewCategoryName(e.target.value)}
                    placeholder="e.g., sports, gaming, travel"
                    className="rm-input flex-1"
                  />
                  <button
                    type="submit"
                    disabled={addingCat}
                    className="rm-btn-secondary shrink-0"
                  >
                    <FolderPlus className="w-4 h-4" />
                    Add Category
                  </button>
                </div>
                {catError && (
                  <p className="text-[13px]" style={{ color: "var(--danger)" }}>
                    {catError}
                  </p>
                )}
              </form>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h3 className="text-[20px] font-semibold">
                    Upload Reference Videos (Optional)
                  </h3>
                  <p className="mt-0.5 text-[14px]" style={{ color: "var(--text-muted)" }}>
                    We recommend 3–5 videos per category (4 minutes or less each). Please upload only licensed or your own content.
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(selectedCategories.length > 0 ? selectedCategories : ["animals"]).map(
                  (cat) => {
                    const catFiles = fileItems.filter((f) => f.category === cat);
                    const totalCount =
                      (categoryCounts[cat] || 0) +
                      catFiles.filter((f) => f.stage === "indexed").length;

                    return (
                      <div key={cat} className="rm-card p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold capitalize text-[15px]">
                            {cat}
                          </span>
                          <span
                            className="text-[13px] px-2 py-0.5 rounded"
                            style={{
                              backgroundColor: "var(--surface-2)",
                              color: "var(--text-muted)",
                            }}
                          >
                            {totalCount} in vault (rec: 3–5)
                          </span>
                        </div>

                        <label
                          htmlFor={`onboard-drop-${cat}`}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            handleFilesSelected(cat, e.dataTransfer.files);
                          }}
                          className="rm-dropzone p-4 block text-center cursor-pointer"
                        >
                          <input
                            id={`onboard-drop-${cat}`}
                            type="file"
                            accept="video/*"
                            multiple
                            className="hidden"
                            onChange={(e) =>
                              handleFilesSelected(cat, e.target.files)
                            }
                          />
                          <Upload
                            className="w-5 h-5 mx-auto mb-1"
                            style={{ color: "var(--accent)" }}
                          />
                          <div className="text-[14px] font-medium">
                            Drop reference videos for{" "}
                            <span className="capitalize">{cat}</span>
                          </div>
                          <div
                            className="text-[13px]"
                            style={{ color: "var(--text-muted)" }}
                          >
                            MP4, MOV, WebM (max 4 min recommended)
                          </div>
                        </label>

                        {catFiles.length > 0 && (
                          <div className="space-y-2 max-h-36 overflow-y-auto">
                            {catFiles.map((item) => (
                              <div
                                key={item.id}
                                className="rm-card-subtle p-2.5 text-[13px] space-y-1"
                              >
                                <div className="flex items-center justify-between gap-2">
                                  <span className="font-medium truncate">
                                    {item.file.name}
                                  </span>
                                  {item.stage === "indexed" && (
                                    <CheckCircle2
                                      className="w-4 h-4 shrink-0"
                                      style={{ color: "var(--success)" }}
                                    />
                                  )}
                                  {(item.stage === "uploading" ||
                                    item.stage === "analyzing") && (
                                    <Loader2
                                      className="w-4 h-4 animate-spin shrink-0"
                                      style={{ color: "var(--accent)" }}
                                    />
                                  )}
                                  {item.stage === "error" && (
                                    <button
                                      type="button"
                                      onClick={() => ingestSingleItem(item)}
                                      className="rm-btn-ghost text-[13px] px-2 py-0.5"
                                    >
                                      <RefreshCw className="w-3.5 h-3.5" /> Retry
                                    </button>
                                  )}
                                </div>
                                <div style={{ color: "var(--text-muted)" }}>
                                  {item.stageLabel}
                                </div>
                                {item.errorMsg && (
                                  <div style={{ color: "var(--danger)" }}>
                                    {item.errorMsg}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center"
                  style={{
                    backgroundColor: "var(--success-soft)",
                    color: "var(--success)",
                  }}
                >
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-[20px] font-semibold">
                    RefMotion Studio is Ready
                  </h3>
                  <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                    Your Reference Vault categories and rendering engines are configured.
                  </p>
                </div>
              </div>

              <div className="rm-card-subtle p-4 space-y-3">
                <div className="font-semibold text-[15px]">
                  Reference Vault Summary by Category
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {categories.map((cat) => (
                    <div key={cat} className="rm-card p-3 flex items-center justify-between">
                      <span className="capitalize font-medium text-[14px]">
                        {cat}
                      </span>
                      <span
                        className="font-semibold text-[14px]"
                        style={{ color: "var(--accent)" }}
                      >
                        {categoryCounts[cat] || 0} videos
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer Controls */}
        <div
          className="px-6 py-4 border-t flex items-center justify-between"
          style={{ backgroundColor: "var(--surface-2)" }}
        >
          <div>
            {step > 1 && (
              <button
                type="button"
                onClick={() => setStep((s) => s - 1)}
                className="rm-btn-secondary"
              >
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {step < 4 ? (
              <>
                <button
                  type="button"
                  onClick={() => handleComplete(false)}
                  className="rm-btn-secondary"
                >
                  Skip Setup
                </button>
                <button
                  type="button"
                  onClick={() => setStep((s) => s + 1)}
                  className="rm-btn-primary"
                >
                  Next <ChevronRight className="w-4 h-4" />
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  disabled={submittingFinish}
                  onClick={() => handleComplete(false)}
                  className="rm-btn-secondary"
                >
                  Go to Studio Hub
                </button>
                <button
                  type="button"
                  disabled={submittingFinish}
                  onClick={() => handleComplete(true)}
                  className="rm-btn-primary"
                >
                  <Sparkles className="w-4 h-4" /> Start the Tour
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
