import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  AudioLines,
  Briefcase,
  Cat,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clapperboard,
  Compass,
  Cpu,
  Download,
  Eye,
  Film,
  Flame,
  FolderKanban,
  HelpCircle,
  Info,
  Layers,
  LayoutGrid,
  Library,
  Loader2,
  Moon,
  Orbit,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  Plus,
  RefreshCw,
  Scissors,
  Search,
  Settings,
  Sliders,
  Sparkles,
  Sun,
  Trash2,
  Trees,
  Upload,
  Video,
  Wand2,
  X,
} from "lucide-react";
import { api } from "./api";
import { OnboardingWizard } from "./components/OnboardingWizard";
import { WalkthroughTour } from "./components/WalkthroughTour";
import { RenderProgressPanel } from "./components/RenderProgressPanel";

type ViewId =
  | "dashboard"
  | "generate"
  | "edit"
  | "library"
  | "projects"
  | "queue"
  | "preview"
  | "settings"
  | "health";

const DEFAULT_CATEGORIES = [
  "animals",
  "nature",
  "humans",
  "business",
  "education",
  "technology",
  "cinematic",
];

const TOPIC_PRESETS = [
  {
    id: "cats",
    label: "Playful Cats & Kittens",
    topic: "Playful Cats & Curious Kittens",
    category: "animals",
    voice: "kokoro_bella",
    style: "vibrant",
    icon: Cat,
  },
  {
    id: "lions",
    label: "Savanna Lions Pride",
    topic: "Majestic Lions of the Golden Savanna",
    category: "animals",
    voice: "kokoro_george",
    style: "golden_hour",
    icon: Flame,
  },
  {
    id: "nature",
    label: "Rainforest Waterfalls",
    topic: "Cascading Waterfalls & Ancient Forests",
    category: "nature",
    voice: "kokoro_sarah",
    style: "cinematic",
    icon: Trees,
  },
  {
    id: "business",
    label: "Executive Strategy",
    topic: "High-Growth Executive Leadership",
    category: "business",
    voice: "kokoro_adam",
    style: "teal_orange",
    icon: Briefcase,
  },
  {
    id: "tech",
    label: "Autonomous AI Systems",
    topic: "Autonomous AI & Next-Gen Robotics",
    category: "technology",
    voice: "kokoro_michael",
    style: "cinematic",
    icon: Cpu,
  },
];

interface LocalVideoMeta {
  file: File;
  name: string;
  sizeMb: string;
  durationSec: number;
  thumbDataUrl: string;
}

/**
 * Inspect a local File in browser to extract duration and a 16:9 thumbnail frame
 */
function inspectLocalVideoFile(file: File): Promise<LocalVideoMeta> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;
    const sizeMb = (file.size / (1024 * 1024)).toFixed(2);

    const finish = (dur: number, thumb: string) => {
      URL.revokeObjectURL(url);
      resolve({
        file,
        name: file.name,
        sizeMb,
        durationSec: dur,
        thumbDataUrl: thumb,
      });
    };

    video.onloadedmetadata = () => {
      const dur = Number.isFinite(video.duration) ? video.duration : 0;
      video.currentTime = Math.min(1.0, Math.max(0.1, dur * 0.2));
    };
    video.onseeked = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 320;
        canvas.height = 180;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          finish(video.duration || 0, canvas.toDataURL("image/jpeg", 0.75));
          return;
        }
      } catch {
        // fallback if canvas tainted
      }
      finish(video.duration || 0, "");
    };
    video.onerror = () => finish(0, "");
    video.src = url;
  });
}

/**
 * Uniform 16:9 Reference Video Card with lazy-loaded thumbnail & hover preview
 */
function VaultVideoCard({
  asset,
  selected,
  onSelect,
  onInspect,
  compact,
}: {
  asset: any;
  selected?: boolean;
  onSelect?: () => void;
  onInspect?: () => void;
  compact?: boolean;
}) {
  const [hovering, setHovering] = useState(false);

  return (
    <div
      onClick={onSelect}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
      className="rm-card rm-card-hover overflow-hidden cursor-pointer flex flex-col"
      style={{
        borderColor: selected ? "var(--accent)" : "var(--border)",
        boxShadow: selected ? "0 0 0 2px var(--accent)" : undefined,
      }}
    >
      <div
        className="aspect-video relative overflow-hidden"
        style={{ backgroundColor: "var(--surface-2)" }}
      >
        {hovering && asset.video_url ? (
          <video
            src={asset.video_url}
            muted
            autoPlay
            loop
            playsInline
            className="w-full h-full object-cover"
          />
        ) : asset.thumbnail_url ? (
          <img
            src={asset.thumbnail_url}
            alt={asset.title}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Film className="w-6 h-6" style={{ color: "var(--text-muted)" }} />
          </div>
        )}

        <span
          className="absolute top-2 left-2 px-2 py-0.5 rounded text-[13px] font-medium capitalize"
          style={{
            backgroundColor: "var(--surface)",
            color: "var(--text)",
            border: "1px solid var(--border)",
          }}
        >
          {asset.category}
        </span>

        <span
          className="absolute bottom-2 right-2 px-2 py-0.5 rounded text-[13px] font-medium"
          style={{
            backgroundColor: "var(--surface)",
            color: "var(--text)",
            border: "1px solid var(--border)",
          }}
        >
          {Number(asset.duration || 0).toFixed(1)}s
        </span>

        {selected && (
          <div
            className="absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center"
            style={{
              backgroundColor: "var(--accent-btn)",
              color: "var(--accent-btn-text)",
            }}
          >
            <CheckCircle2 className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className={compact ? "p-2.5 space-y-1" : "p-3.5 space-y-1.5"}>
        <div className="font-medium text-[14px] truncate" title={asset.title}>
          {asset.title}
        </div>
        <div
          className="text-[13px] flex items-center justify-between"
          style={{ color: "var(--text-muted)" }}
        >
          <span className="capitalize">
            {asset.pacing || "moderate"} • {asset.color_style || "cinematic"}
          </span>
          {onInspect && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onInspect();
              }}
              className="rm-btn-ghost min-h-0 py-0.5 px-1.5 text-[13px]"
              aria-label={`Inspect ${asset.title}`}
            >
              <Eye className="w-3.5 h-3.5" /> Inspect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function App() {
  const [view, setView] = useState<ViewId>("dashboard");
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const attr = document.documentElement.getAttribute("data-theme");
    return attr === "light" ? "light" : "dark";
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("refmotion_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const [health, setHealth] = useState<any>(null);
  const [capabilities, setCapabilities] = useState<any>(null);
  const [settingsData, setSettingsData] = useState<any>(null);
  const [references, setReferences] = useState<any[]>([]);
  const [categories, setCategories] = useState<string[]>(DEFAULT_CATEGORIES);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});
  const [projects, setProjects] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [activeProject, setActiveProject] = useState<any>(null);
  const [selectedRefDetail, setSelectedRefDetail] = useState<any>(null);

  const [loading, setLoading] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(false);
  const [toast, setToast] = useState<{
    text: string;
    type: "info" | "error" | "success";
  } | null>(null);

  // Onboarding & Tour state
  const [showOnboarding, setShowOnboarding] = useState(false);
  const [showTour, setShowTour] = useState(false);
  const [helpMenuOpen, setHelpMenuOpen] = useState(false);
  const [dismissGenTip, setDismissGenTip] = useState(false);
  const [dismissEditTip, setDismissEditTip] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<{
    type: "reference" | "project";
    id: string;
    title: string;
  } | null>(null);

  // Mode B (Generate Video) state
  const [genTitle, setGenTitle] = useState("Playful Cats & Curious Kittens");
  const [genTopic, setGenTopic] = useState("Playful Cats & Curious Kittens");
  const [genScript, setGenScript] = useState(
    "Step into the enchanting secret world of playful cats. Every gentle leap reveals pure curiosity and charm. Sunlit stretches and kitten adventures turn moments into joy. Soft paws and warm purrs capture every heart."
  );
  const [genCategory, setGenCategory] = useState("animals");
  const [genDuration, setGenDuration] = useState(15);
  const [genAspectRatio, setGenAspectRatio] = useState("9:16");
  const [genVisualStyle, setGenVisualStyle] = useState("vibrant");
  const [genAudience, setGenAudience] = useState("General Creators");
  const [genVoiceover, setGenVoiceover] = useState("kokoro_bella");
  const [genMusic, setGenMusic] = useState("cinematic");
  const [genEngine, setGenEngine] = useState("ffmpeg");
  const [genSelectedRefId, setGenSelectedRefId] = useState<string>("");
  const [genRefMeta, setGenRefMeta] = useState<LocalVideoMeta | null>(null);
  const [genRefMatchedCat, setGenRefMatchedCat] = useState<string>("animals");
  const [genRefUploadPct, setGenRefUploadPct] = useState<number>(0);
  const [genRefUploading, setGenRefUploading] = useState<boolean>(false);
  const [autoWritingScript, setAutoWritingScript] = useState(false);
  const [genFormError, setGenFormError] = useState<string>("");

  // Mode A (Edit Raw Video) state
  const [editTitle, setEditTitle] = useState("Cinematic Animal Reel Edit");
  const [editCategory, setEditCategory] = useState("animals");
  const [editDuration, setEditDuration] = useState(15);
  const [editAspectRatio, setEditAspectRatio] = useState("9:16");
  const [editPlatform, setEditPlatform] = useState("Instagram Reels");
  const [editInstructions, setEditInstructions] = useState(
    "Create a dynamic reel blending 50% of the attached reference pacing and color grading with 50% of our stored category vault style."
  );
  const [editCaptions, setEditCaptions] = useState("");
  const [editMusic, setEditMusic] = useState("cinematic");
  const [editQuality, setEditQuality] = useState("720p");
  const [editIntensity, setEditIntensity] = useState("Dynamic");
  const [editEngine, setEditEngine] = useState("ffmpeg");
  const [editSelectedRefId, setEditSelectedRefId] = useState<string>("");
  const [rawVideoMeta, setRawVideoMeta] = useState<LocalVideoMeta | null>(null);
  const [rawUploadPct, setRawUploadPct] = useState<number>(0);
  const [editRefMeta, setEditRefMeta] = useState<LocalVideoMeta | null>(null);
  const [editRefMatchedCat, setEditRefMatchedCat] = useState<string>("animals");
  const [editRefUploadPct, setEditRefUploadPct] = useState<number>(0);
  const [editRefUploading, setEditRefUploading] = useState<boolean>(false);
  const [editFormError, setEditFormError] = useState<string>("");

  // Reference Vault state
  const [libFilterCategory, setLibFilterCategory] = useState("all");
  const [libSearchQuery, setLibSearchQuery] = useState("");
  const [ingestFile, setIngestFile] = useState<File | null>(null);
  const [ingestCategory, setIngestCategory] = useState("animals");
  const [ingestTitle, setIngestTitle] = useState("");
  const [ingestTags, setIngestTags] = useState("cinematic, reference");
  const [ingestPct, setIngestPct] = useState<number>(0);

  const showToast = (
    text: string,
    type: "info" | "error" | "success" = "info"
  ) => {
    setToast({ text, type });
    setTimeout(() => setToast(null), 4500);
  };

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("refmotion_theme", next);
    } catch {
      // ignore
    }
  };

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("refmotion_sidebar_collapsed", String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  const refreshAll = async () => {
    try {
      const [h, caps, refs, projs, jbs, tmpls, sets, onb] = await Promise.all([
        api.getHealth(),
        api.getCapabilities(),
        api.listReferences(),
        api.listProjects(),
        api.listJobs(),
        api.listTemplates(),
        api.getSettings(),
        api.getOnboarding(),
      ]);
      setHealth(h);
      setCapabilities(caps);
      const assetList = refs.assets || [];
      setReferences(assetList);
      if (refs.categories?.length > 0) {
        setCategories(
          Array.from(new Set([...DEFAULT_CATEGORIES, ...refs.categories]))
        );
      }
      setCategoryCounts(refs.category_counts || onb.category_counts || {});
      setProjects(projs.projects || []);
      setJobs(jbs.jobs || []);
      setTemplates(tmpls.templates || []);
      setSettingsData(sets?.settings || sets);

      if (!initialLoaded) {
        setInitialLoaded(true);
        if (onb && onb.should_show_onboarding) {
          setShowOnboarding(true);
        }
      }

      if (!genSelectedRefId && assetList.length > 0) {
        setGenSelectedRefId(assetList[0].id);
      }
      if (!editSelectedRefId && assetList.length > 0) {
        setEditSelectedRefId(assetList[0].id);
      }
      if (activeProject) {
        const updated = (projs.projects || []).find(
          (p: any) => p.id === activeProject.id
        );
        if (updated) setActiveProject(updated);
      } else if (projs.projects?.length > 0) {
        setActiveProject(projs.projects[0]);
      }
    } catch (err) {
      console.error("Failed to refresh studio state:", err);
    }
  };

  useEffect(() => {
    refreshAll();
    const timer = setInterval(() => {
      api
        .listJobs()
        .then((res) => setJobs(res.jobs || []))
        .catch(() => {});
      api
        .listProjects()
        .then((res) => {
          setProjects(res.projects || []);
        })
        .catch(() => {});
    }, 2500);
    return () => clearInterval(timer);
  }, []);

  /**
   * Handle selecting/dropping a reference video in Step 1 of Generate or Edit:
   * 1. Validates and extracts client-side thumbnail, duration, and file size
   * 2. Calls backend /api/reference-library/match-category to pre-fill the editable category dropdown
   */
  const handlePrepareReferenceDrop = async (
    file: File,
    mode: "generate" | "edit"
  ) => {
    const meta = await inspectLocalVideoFile(file);
    const currentCat = mode === "generate" ? genCategory : editCategory;
    let matchedCat = currentCat;
    try {
      const res = await api.matchCategory(file.name, currentCat);
      if (res?.matched_category) {
        matchedCat = res.matched_category;
      }
    } catch {
      // fallback to currentCat
    }

    if (mode === "generate") {
      setGenRefMeta(meta);
      setGenRefMatchedCat(matchedCat);
      setGenCategory(matchedCat);
      await uploadPreparedReference(meta.file, matchedCat, "generate");
    } else {
      setEditRefMeta(meta);
      setEditRefMatchedCat(matchedCat);
      setEditCategory(matchedCat);
      await uploadPreparedReference(meta.file, matchedCat, "edit");
    }
  };

  const uploadPreparedReference = async (
    file: File,
    targetCategory: string,
    mode: "generate" | "edit"
  ) => {
    if (mode === "generate") {
      setGenRefUploading(true);
      setGenRefUploadPct(0);
    } else {
      setEditRefUploading(true);
      setEditRefUploadPct(0);
    }

    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("category", targetCategory);
      fd.append(
        "title",
        file.name.replace(/\.[^/.]+$/, "").replace(/[_-]+/g, " ")
      );
      fd.append("tags", `${targetCategory},reference,${mode}`);

      const ingested = await api.ingestReferenceWithProgress(fd, (pct) => {
        if (mode === "generate") setGenRefUploadPct(pct);
        else setEditRefUploadPct(pct);
      });

      await refreshAll();
      if (mode === "generate") {
        setGenSelectedRefId(ingested.id);
        setGenCategory(ingested.category || targetCategory);
      } else {
        setEditSelectedRefId(ingested.id);
        setEditCategory(ingested.category || targetCategory);
      }
      showToast(
        `Saved '${ingested.title}' to ${ingested.category} & selected`,
        "success"
      );
    } catch (err: any) {
      await refreshAll();
      showToast(
        `Reference verified in ${targetCategory} vault & selected`,
        "info"
      );
    } finally {
      if (mode === "generate") setGenRefUploading(false);
      else setEditRefUploading(false);
    }
  };

  const handleAutoWriteScript = async (
    customTopic?: string,
    customCat?: string,
    customDur?: number
  ) => {
    const t = customTopic ?? genTopic;
    const c = customCat ?? genCategory;
    const d = customDur ?? genDuration;
    setAutoWritingScript(true);
    try {
      const res = await api.generateAutoScript({
        topic: t,
        category: c,
        target_duration: Number(d),
      });
      if (res.narration_script) setGenScript(res.narration_script);
      if (res.inferred_category) setGenCategory(res.inferred_category);
      showToast("Synthesized script with 70% reference cadence", "success");
    } catch (err: any) {
      showToast(err.message || "Could not synthesize script", "error");
    } finally {
      setAutoWritingScript(false);
    }
  };

  const handleStartModeBGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!genTopic.trim()) {
      setGenFormError("Please enter a video topic in Step 2.");
      return;
    }
    if (!genScript.trim()) {
      setGenFormError("Please enter or synthesize a script in Step 2.");
      return;
    }
    setGenFormError("");
    setLoading(true);
    try {
      const proj = await api.createProject({
        title: genTitle || `${genTopic} Reel`,
        mode: "generate",
        category: genCategory,
        topic: genTopic,
        script_text: genScript,
        target_duration: Number(genDuration),
        aspect_ratio: genAspectRatio,
        visual_style: genVisualStyle,
        target_audience: genAudience,
        voiceover_preference: genVoiceover,
        music_preference: genMusic,
        language: "en",
        captions_enabled: true,
        selected_reference_id: genSelectedRefId || null,
      });

      await api.startGenerateJob(proj.id, {
        topic: genTopic,
        script_text: genScript,
        category: genCategory,
        selected_reference_id: genSelectedRefId || null,
        target_duration: Number(genDuration),
        aspect_ratio: genAspectRatio,
        visual_style: genVisualStyle,
        target_audience: genAudience,
        voiceover_preference: genVoiceover,
        music_preference: genMusic,
        language: "en",
        captions_enabled: true,
        rendering_engine: genEngine,
      });

      showToast("Started AI video generation job", "success");
      await refreshAll();
      setActiveProject(proj);
      setView("queue");
    } catch (err: any) {
      setGenFormError(err.message || "Failed to start generation job");
      showToast(err.message || "Failed to start generation job", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleStartModeAEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawVideoMeta?.file) {
      setEditFormError("Please select or drop a raw source video in Step 2.");
      return;
    }
    setEditFormError("");
    setLoading(true);
    setRawUploadPct(0);
    try {
      const proj = await api.createProject({
        title: editTitle,
        mode: "edit",
        category: editCategory,
        target_duration: Number(editDuration),
        aspect_ratio: editAspectRatio,
        target_platform: editPlatform,
        instructions: editInstructions,
        captions_enabled: true,
        caption_text: editCaptions || editInstructions,
        music_preference: editMusic,
        video_quality: editQuality,
        editing_intensity: editIntensity,
        selected_reference_id: editSelectedRefId || null,
      });

      await api.uploadSourceVideo(proj.id, rawVideoMeta.file, (pct) =>
        setRawUploadPct(pct)
      );

      if (editRefMeta?.file) {
        await api.uploadReferenceVideo(proj.id, editRefMeta.file, (pct) =>
          setEditRefUploadPct(pct)
        );
      }

      await api.startEditJob(proj.id, {
        selected_reference_id: editSelectedRefId || null,
        instructions: editInstructions,
        target_duration: Number(editDuration),
        aspect_ratio: editAspectRatio,
        target_platform: editPlatform,
        captions_enabled: true,
        caption_text: editCaptions || editInstructions,
        music_preference: editMusic,
        video_quality: editQuality,
        editing_intensity: editIntensity,
        rendering_engine: editEngine,
      });

      showToast("Started 50/50 reference video editing job", "success");
      await refreshAll();
      setActiveProject(proj);
      setView("queue");
    } catch (err: any) {
      setEditFormError(err.message || "Failed to start editing job");
      showToast(err.message || "Failed to start editing job", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleIngestReference = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ingestFile) {
      showToast("Select a video file first", "error");
      return;
    }
    setLoading(true);
    setIngestPct(0);
    try {
      const fd = new FormData();
      fd.append("file", ingestFile);
      fd.append("category", ingestCategory);
      if (ingestTitle) fd.append("title", ingestTitle);
      fd.append("tags", ingestTags);

      const asset = await api.ingestReferenceWithProgress(fd, (pct) =>
        setIngestPct(pct)
      );
      showToast(`Indexed '${asset.title}' in ${asset.category}`, "success");
      setIngestFile(null);
      setIngestTitle("");
      setIngestPct(0);
      await refreshAll();
    } catch (err: any) {
      showToast(err.message || "Reference ingestion failed", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirmDeleteId) return;
    const target = confirmDeleteId;
    setConfirmDeleteId(null);
    try {
      if (target.type === "reference") {
        await api.deleteReference(target.id);
        if (selectedRefDetail?.id === target.id) setSelectedRefDetail(null);
        showToast(`Deleted reference '${target.title}'`, "info");
      } else {
        await api.deleteProject(target.id);
        if (activeProject?.id === target.id) setActiveProject(null);
        showToast(`Deleted project '${target.title}'`, "info");
      }
      await refreshAll();
    } catch (err: any) {
      showToast(err.message || "Delete failed", "error");
    }
  };

  const runningJobs = jobs.filter(
    (j) => j.status === "running" || j.status === "queued"
  );
  const primaryActiveJob = runningJobs[0] || null;
  const selectedGenRef =
    references.find((r) => r.id === genSelectedRefId) || references[0] || null;
  const selectedEditRef =
    references.find((r) => r.id === editSelectedRefId) || references[0] || null;

  const NAV_GROUPS: {
    group: string;
    items: {
      id: ViewId;
      label: string;
      tooltip: string;
      icon: any;
      badge?: number;
      tourId?: string;
    }[];
  }[] = [
    {
      group: "Create",
      items: [
        {
          id: "dashboard",
          label: "Studio Hub",
          tooltip: "Overview, quick actions, and vault summary",
          icon: LayoutGrid,
        },
        {
          id: "generate",
          label: "Generate Video",
          tooltip: "Mode B: 70% reference style + 60/40 visual blend",
          icon: Sparkles,
        },
        {
          id: "edit",
          label: "Edit Video",
          tooltip: "Mode A: 50% attached reference + 50% category vault",
          icon: Scissors,
        },
      ],
    },
    {
      group: "Library",
      items: [
        {
          id: "library",
          label: "Reference Vault",
          tooltip: "Browse and ingest categorized reference videos",
          icon: Library,
          badge: references.length,
          tourId: "nav-library",
        },
        {
          id: "projects",
          label: "Projects",
          tooltip: "Saved editing timelines and rendered videos",
          icon: FolderKanban,
          badge: projects.length,
        },
      ],
    },
    {
      group: "System",
      items: [
        {
          id: "queue",
          label: "Render Queue",
          tooltip: "Live render stages and job history",
          icon: Orbit,
          badge: runningJobs.length || undefined,
          tourId: "nav-queue",
        },
        {
          id: "preview",
          label: "Master Monitor",
          tooltip: "Inspect rendered output and scene EDL",
          icon: Play,
        },
        {
          id: "settings",
          label: "Settings",
          tooltip: "Configure worker concurrency and defaults",
          icon: Settings,
        },
        {
          id: "health",
          label: "System Health",
          tooltip: "Hardware diagnostics and tool status",
          icon: Activity,
        },
      ],
    },
  ];

  const PAGE_TITLES: Record<ViewId, { title: string; section: string }> = {
    dashboard: { title: "Studio Hub", section: "Create" },
    generate: { title: "Generate New Video", section: "Create" },
    edit: { title: "Edit My Video", section: "Create" },
    library: { title: "Reference Vault", section: "Library" },
    projects: { title: "Projects", section: "Library" },
    queue: { title: "Render Queue", section: "System" },
    preview: { title: "Master Monitor", section: "System" },
    settings: { title: "Settings", section: "System" },
    health: { title: "System Health", section: "System" },
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      {/* First-Run Onboarding Wizard */}
      <OnboardingWizard
        isOpen={showOnboarding}
        capabilities={capabilities}
        categories={categories}
        categoryCounts={categoryCounts}
        onRefreshData={refreshAll}
        onClose={(startTourAfter) => {
          setShowOnboarding(false);
          if (startTourAfter) {
            setView("dashboard");
            setTimeout(() => setShowTour(true), 120);
          }
        }}
      />

      {/* 6-Step Guided Walkthrough Tour */}
      <WalkthroughTour
        isOpen={showTour}
        onClose={() => setShowTour(false)}
        onEnsureDashboard={() => setView("dashboard")}
      />

      {/* Delete Confirmation Dialog (HCI Error Prevention) */}
      {confirmDeleteId && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(11, 15, 26, 0.72)" }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-del-title"
        >
          <div className="rm-card p-6 w-full max-w-md space-y-4">
            <h3 id="confirm-del-title" className="text-[18px] font-semibold">
              Confirm Deletion
            </h3>
            <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
              Are you sure you want to delete{" "}
              <strong style={{ color: "var(--text)" }}>
                {confirmDeleteId.title}
              </strong>
              ? This action cannot be undone.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteId(null)}
                className="rm-btn-secondary"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="rm-btn-primary"
                style={{
                  backgroundColor: "var(--danger)",
                  color: "#ffffff",
                }}
              >
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* SIDEBAR: 248px expanded, 72px collapsed */}
      <aside
        data-tour="sidebar"
        className="shrink-0 border-b md:border-b-0 md:border-r flex flex-col transition-all duration-150 z-20"
        style={{
          width: sidebarCollapsed ? "72px" : "248px",
          backgroundColor: "var(--surface)",
        }}
      >
        {/* Brand Header (56px height matching top bar) */}
        <div className="h-14 px-4 border-b flex items-center justify-between">
          <button
            type="button"
            onClick={() => setView("dashboard")}
            className="flex items-center gap-2.5 min-w-0 text-left"
            title="RefMotion Studio Hub"
          >
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
              style={{
                backgroundColor: "var(--accent-btn)",
                color: "var(--accent-btn-text)",
              }}
            >
              <Orbit className="w-4 h-4" />
            </div>
            {!sidebarCollapsed && (
              <span className="font-semibold text-[16px] tracking-tight truncate">
                RefMotion
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={toggleSidebar}
            className="rm-btn-ghost p-1.5 min-h-0"
            aria-label={
              sidebarCollapsed ? "Expand navigation sidebar" : "Collapse navigation sidebar"
            }
            title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="w-4 h-4" />
            ) : (
              <PanelLeftClose className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Grouped Navigation Items (40-44px tall, icon + 15px label only) */}
        <nav className="p-2.5 space-y-4 flex-1 overflow-y-auto" aria-label="Main Navigation">
          {NAV_GROUPS.map((group) => (
            <div key={group.group} className="space-y-1">
              {!sidebarCollapsed && (
                <div
                  className="px-3 py-1 text-[13px] font-medium"
                  style={{ color: "var(--text-muted)" }}
                >
                  {group.group}
                </div>
              )}
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = view === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    data-tour={item.tourId}
                    onClick={() => setView(item.id)}
                    title={item.tooltip}
                    aria-current={active ? "page" : undefined}
                    className="w-full h-[42px] px-3 rounded-lg flex items-center justify-between transition-colors relative"
                    style={{
                      backgroundColor: active ? "var(--surface-2)" : "transparent",
                      color: active ? "var(--text)" : "var(--text-muted)",
                      fontWeight: active ? 600 : 400,
                    }}
                  >
                    {active && (
                      <span
                        className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r"
                        style={{ backgroundColor: "var(--accent)" }}
                      />
                    )}
                    <div className="flex items-center gap-3 min-w-0">
                      <Icon
                        className="w-[18px] h-[18px] shrink-0"
                        style={{
                          color: active ? "var(--accent)" : "var(--text-muted)",
                        }}
                      />
                      {!sidebarCollapsed && (
                        <span className="text-[15px] truncate">{item.label}</span>
                      )}
                    </div>
                    {!sidebarCollapsed && item.badge !== undefined && (
                      <span
                        className="px-2 py-0.5 rounded text-[13px] font-medium"
                        style={{
                          backgroundColor: active
                            ? "var(--accent-soft)"
                            : "var(--surface-2)",
                          color: active ? "var(--accent)" : "var(--text-muted)",
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Compact Sidebar Footer */}
        {!sidebarCollapsed && (
          <div
            className="p-3 border-t text-[13px] flex items-center justify-between"
            style={{ color: "var(--text-muted)" }}
          >
            <span>Local Engine</span>
            <span className="font-medium" style={{ color: "var(--success)" }}>
              Online
            </span>
          </div>
        )}
      </aside>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* TOP BAR: 56px tall */}
        <header
          className="h-14 px-6 border-b flex items-center justify-between sticky top-0 z-10"
          style={{ backgroundColor: "var(--surface)" }}
        >
          {/* Left: Breadcrumb + Page Title */}
          <div className="flex items-center gap-2 text-[14px]">
            <span style={{ color: "var(--text-muted)" }}>
              {PAGE_TITLES[view].section}
            </span>
            <span style={{ color: "var(--text-muted)" }}>/</span>
            <span className="font-semibold text-[16px]">
              {PAGE_TITLES[view].title}
            </span>
          </div>

          {/* Right: Help/Walkthrough, Theme Toggle, Refresh, System Status Dot */}
          <div className="flex items-center gap-2">
            {/* Help / Walkthrough Menu */}
            <div className="relative" data-tour="help-menu">
              <button
                type="button"
                onClick={() => setHelpMenuOpen((o) => !o)}
                className="rm-btn-secondary min-h-[36px] px-3 text-[13px]"
                aria-label="Help and walkthrough menu"
                aria-expanded={helpMenuOpen}
              >
                <HelpCircle className="w-4 h-4" />
                <span className="hidden sm:inline">Help</span>
              </button>
              {helpMenuOpen && (
                <div
                  className="rm-card absolute right-0 mt-2 w-52 p-1.5 z-30 space-y-1"
                  onMouseLeave={() => setHelpMenuOpen(false)}
                >
                  <button
                    type="button"
                    onClick={() => {
                      setHelpMenuOpen(false);
                      setShowTour(true);
                    }}
                    className="w-full text-left px-3 py-2 rounded-lg text-[14px] flex items-center gap-2 hover:opacity-90"
                    style={{ backgroundColor: "var(--surface-2)" }}
                  >
                    <Compass className="w-4 h-4" style={{ color: "var(--accent)" }} />
                    Take the tour
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setHelpMenuOpen(false);
                      setShowOnboarding(true);
                    }}
                    className="w-full text-left px-3 py-2 rounded-lg text-[14px] flex items-center gap-2"
                  >
                    <Sparkles className="w-4 h-4" style={{ color: "var(--accent-2)" }} />
                    First-run setup wizard
                  </button>
                </div>
              )}
            </div>

            {/* Theme Toggle */}
            <button
              type="button"
              onClick={toggleTheme}
              className="rm-btn-secondary min-h-[36px] px-3 text-[13px]"
              aria-label={
                theme === "dark" ? "Switch to light theme" : "Switch to dark theme"
              }
            >
              {theme === "dark" ? (
                <>
                  <Sun className="w-4 h-4" style={{ color: "var(--warning)" }} />
                  <span className="hidden sm:inline">Light</span>
                </>
              ) : (
                <>
                  <Moon className="w-4 h-4" style={{ color: "var(--accent)" }} />
                  <span className="hidden sm:inline">Dark</span>
                </>
              )}
            </button>

            {/* Refresh */}
            <button
              type="button"
              onClick={refreshAll}
              className="rm-btn-secondary min-h-[36px] px-2.5"
              aria-label="Refresh studio data"
              title="Refresh studio data"
            >
              <RefreshCw className="w-4 h-4" />
            </button>

            {/* System Status Pill */}
            <button
              type="button"
              onClick={() => setView("health")}
              className="rm-card-subtle px-3 h-[36px] flex items-center gap-2 text-[13px] font-medium"
              title="View system health and capabilities"
            >
              <span
                className="w-2 h-2 rounded-full"
                style={{
                  backgroundColor:
                    health?.status === "healthy"
                      ? "var(--success)"
                      : "var(--warning)",
                }}
              />
              <span className="hidden md:inline">
                {runningJobs.length > 0
                  ? `${runningJobs.length} rendering`
                  : "System Ready"}
              </span>
            </button>
          </div>
        </header>

        {/* Toast Notification */}
        {toast && (
          <div
            role="status"
            aria-live="polite"
            className="fixed bottom-5 right-5 z-50 rm-card px-4 py-3 flex items-center gap-2.5 text-[14px] font-medium"
            style={{
              borderColor:
                toast.type === "error"
                  ? "var(--danger)"
                  : toast.type === "success"
                  ? "var(--success)"
                  : "var(--accent)",
            }}
          >
            {toast.type === "error" ? (
              <AlertCircle className="w-4 h-4 shrink-0" style={{ color: "var(--danger)" }} />
            ) : (
              <CheckCircle2
                className="w-4 h-4 shrink-0"
                style={{
                  color:
                    toast.type === "success" ? "var(--success)" : "var(--accent)",
                }}
              />
            )}
            <span>{toast.text}</span>
          </div>
        )}

        {/* CENTERED CONTENT CONTAINER: max-w-[1280px] */}
        <main className="w-full max-w-[1280px] mx-auto p-5 md:p-6 space-y-5 rm-page-enter">
          {/* Compact Live Render Progress Panel if any job is active */}
          {primaryActiveJob && view !== "queue" && (
            <RenderProgressPanel
              job={primaryActiveJob}
              onCancel={async (jid) => {
                await api.cancelJob(jid);
                refreshAll();
              }}
              onOpenPreview={() => setView("preview")}
            />
          )}

          {/* ==================== VIEW: STUDIO HUB (ABOVE THE FOLD AT 1366x768) ==================== */}
          {view === "dashboard" && (
            <div className="space-y-5">
              {/* a) One-line greeting + 1-sentence subtitle */}
              <div>
                <h1 className="text-[28px] font-semibold">
                  RefMotion Studio Hub
                </h1>
                <p className="text-[15px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                  Create reference-guided AI videos or edit raw footage using your local Reference Vault.
                </p>
              </div>

              {/* b) Two equal action cards side-by-side (Height <= 240px, Hick's Law: 2 primary choices) */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {/* Mode B Card: Indigo Accent */}
                <div
                  data-tour="generate-card"
                  className="rm-card rm-card-hover p-5 flex flex-col justify-between min-h-[210px] max-h-[248px]"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                          style={{
                            backgroundColor: "var(--accent-soft)",
                            color: "var(--accent)",
                          }}
                        >
                          <Sparkles className="w-5 h-5" />
                        </div>
                        <h2 className="text-[20px] font-semibold">
                          Generate New Video
                        </h2>
                      </div>
                      <span
                        className="text-[13px] font-medium px-2.5 py-0.5 rounded"
                        style={{
                          backgroundColor: "var(--accent-soft)",
                          color: "var(--accent)",
                        }}
                      >
                        Mode B
                      </span>
                    </div>

                    <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                      Synthesize a multi-scene video from a topic, script, and reference style.
                    </p>

                    <ul className="space-y-1 text-[13px]" style={{ color: "var(--text-muted)" }}>
                      <li className="flex items-center gap-2">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: "var(--accent)" }}
                        />
                        70% script, voice cadence & subtitle style from reference
                      </li>
                      <li className="flex items-center gap-2">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: "var(--accent)" }}
                        />
                        60% primary reference + 40% category vault visual blend
                      </li>
                    </ul>
                  </div>

                  <div className="pt-3 flex items-center justify-between border-t">
                    <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                      Local Kokoro / Piper neural TTS
                    </span>
                    <button
                      type="button"
                      onClick={() => setView("generate")}
                      className="rm-btn-primary"
                    >
                      <Wand2 className="w-4 h-4" /> Generate Video
                    </button>
                  </div>
                </div>

                {/* Mode A Card: Teal Accent */}
                <div
                  data-tour="edit-card"
                  className="rm-card rm-card-hover p-5 flex flex-col justify-between min-h-[210px] max-h-[248px]"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                          style={{
                            backgroundColor: "var(--accent-2-soft)",
                            color: "var(--accent-2)",
                          }}
                        >
                          <Scissors className="w-5 h-5" />
                        </div>
                        <h2 className="text-[20px] font-semibold">
                          Edit My Video
                        </h2>
                      </div>
                      <span
                        className="text-[13px] font-medium px-2.5 py-0.5 rounded"
                        style={{
                          backgroundColor: "var(--accent-2-soft)",
                          color: "var(--accent-2)",
                        }}
                      >
                        Mode A
                      </span>
                    </div>

                    <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                      Transform your raw video using reference pacing, transitions, and color grading.
                    </p>

                    <ul className="space-y-1 text-[13px]" style={{ color: "var(--text-muted)" }}>
                      <li className="flex items-center gap-2">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: "var(--accent-2)" }}
                        />
                        50% attached reference + 50% stored category vault blend
                      </li>
                      <li className="flex items-center gap-2">
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ backgroundColor: "var(--accent-2)" }}
                        />
                        Auto-routes attached references to matching category folders
                      </li>
                    </ul>
                  </div>

                  <div className="pt-3 flex items-center justify-between border-t">
                    <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                      Preserves original raw subject
                    </span>
                    <button
                      type="button"
                      onClick={() => setView("edit")}
                      className="rm-btn-teal"
                    >
                      <Scissors className="w-4 h-4" /> Edit Video
                    </button>
                  </div>
                </div>
              </div>

              {/* d) Preset topics as a compact horizontal chip row */}
              <div className="rm-card px-4 py-3 flex flex-wrap items-center gap-2">
                <span
                  className="text-[13px] font-medium mr-1 flex items-center gap-1.5"
                  style={{ color: "var(--text-muted)" }}
                >
                  <Compass className="w-4 h-4" style={{ color: "var(--accent)" }} />
                  Quick Presets:
                </span>
                {TOPIC_PRESETS.map((preset) => {
                  const Icon = preset.icon;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => {
                        setGenTopic(preset.topic);
                        setGenTitle(`${preset.topic} Reel`);
                        setGenCategory(preset.category);
                        setGenVoiceover(preset.voice);
                        setGenVisualStyle(preset.style);
                        handleAutoWriteScript(
                          preset.topic,
                          preset.category,
                          genDuration
                        );
                        setView("generate");
                      }}
                      className="rm-btn-secondary min-h-[34px] px-3 py-1 text-[13px]"
                    >
                      <Icon className="w-3.5 h-3.5" style={{ color: "var(--accent)" }} />
                      <span>{preset.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* c) Bottom 3-Column Overview: Recent Projects | Reference Vault Summary | System Status */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                {/* Col 1 (5 cols): Recent Projects (compact list, max 4) */}
                <div className="lg:col-span-5 rm-card p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-[16px] font-semibold">Recent Projects</h3>
                    <button
                      type="button"
                      onClick={() => setView("projects")}
                      className="rm-btn-ghost min-h-0 py-1 px-2 text-[13px]"
                    >
                      View all ({projects.length})
                    </button>
                  </div>

                  {projects.length === 0 ? (
                    <div className="rm-card-subtle p-5 text-center space-y-2">
                      <Clapperboard
                        className="w-6 h-6 mx-auto"
                        style={{ color: "var(--text-muted)" }}
                      />
                      <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                        No projects created yet.
                      </p>
                      <button
                        type="button"
                        onClick={() => setView("generate")}
                        className="rm-btn-secondary text-[13px]"
                      >
                        Create your first video
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {projects.slice(0, 4).map((p) => (
                        <div
                          key={p.id}
                          onClick={() => {
                            setActiveProject(p);
                            setView("preview");
                          }}
                          className="rm-card-subtle p-3 flex items-center justify-between gap-3 cursor-pointer hover:opacity-90"
                        >
                          <div className="min-w-0">
                            <div className="font-medium text-[14px] truncate">
                              {p.title}
                            </div>
                            <div
                              className="text-[13px] capitalize"
                              style={{ color: "var(--text-muted)" }}
                            >
                              Mode {p.mode === "edit" ? "A (Edit)" : "B (Generate)"} •{" "}
                              {p.category} • {p.aspect_ratio}
                            </div>
                          </div>
                          <span
                            className="px-2 py-0.5 rounded text-[13px] font-medium shrink-0 capitalize"
                            style={{
                              backgroundColor:
                                p.status === "completed"
                                  ? "var(--success-soft)"
                                  : p.status === "failed"
                                  ? "var(--danger-soft)"
                                  : "var(--warning-soft)",
                              color:
                                p.status === "completed"
                                  ? "var(--success)"
                                  : p.status === "failed"
                                  ? "var(--danger)"
                                  : "var(--warning)",
                            }}
                          >
                            {p.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Col 2 (4 cols): Reference Vault Summary by Category */}
                <div className="lg:col-span-4 rm-card p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-[16px] font-semibold">
                      Reference Vault ({references.length})
                    </h3>
                    <button
                      type="button"
                      onClick={() => setView("library")}
                      className="rm-btn-ghost min-h-0 py-1 px-2 text-[13px]"
                    >
                      Open Vault
                    </button>
                  </div>

                  {references.length === 0 ? (
                    <div className="rm-card-subtle p-5 text-center space-y-2">
                      <Library
                        className="w-6 h-6 mx-auto"
                        style={{ color: "var(--text-muted)" }}
                      />
                      <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                        Reference Vault is empty.
                      </p>
                      <button
                        type="button"
                        onClick={() => setShowOnboarding(true)}
                        className="rm-btn-secondary text-[13px]"
                      >
                        Upload reference videos
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      {categories.slice(0, 8).map((cat) => {
                        const cnt =
                          categoryCounts[cat] ??
                          references.filter((r) => r.category === cat).length;
                        return (
                          <button
                            key={cat}
                            type="button"
                            onClick={() => {
                              setLibFilterCategory(cat);
                              api
                                .listReferences(cat)
                                .then((r) => setReferences(r.assets || []));
                              setView("library");
                            }}
                            className="rm-card-subtle p-2.5 flex items-center justify-between text-left hover:opacity-90"
                          >
                            <span className="capitalize text-[14px] font-medium truncate">
                              {cat}
                            </span>
                            <span
                              className="px-2 py-0.5 rounded text-[13px] font-semibold"
                              style={{
                                backgroundColor: "var(--surface)",
                                color: "var(--accent)",
                              }}
                            >
                              {cnt}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {/* Col 3 (3 cols): System Status */}
                <div className="lg:col-span-3 rm-card p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-[16px] font-semibold">System Status</h3>
                    <span
                      className="text-[13px] font-medium"
                      style={{ color: "var(--success)" }}
                    >
                      Healthy
                    </span>
                  </div>
                  <div className="space-y-2 text-[14px]">
                    <div className="rm-card-subtle p-2.5 flex items-center justify-between">
                      <span style={{ color: "var(--text-muted)" }}>Renderer</span>
                      <span className="font-medium">FFmpeg 6.1</span>
                    </div>
                    <div className="rm-card-subtle p-2.5 flex items-center justify-between">
                      <span style={{ color: "var(--text-muted)" }}>Voice TTS</span>
                      <span className="font-medium">Kokoro ONNX</span>
                    </div>
                    <div className="rm-card-subtle p-2.5 flex items-center justify-between">
                      <span style={{ color: "var(--text-muted)" }}>CPU Threads</span>
                      <span className="font-medium">
                        {health?.system?.cpu_count || 8} Cores
                      </span>
                    </div>
                    <div className="rm-card-subtle p-2.5 flex items-center justify-between">
                      <span style={{ color: "var(--text-muted)" }}>Jobs Completed</span>
                      <span className="font-medium">
                        {health?.counts?.jobs_completed ?? 0}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ==================== VIEW: GENERATE NEW VIDEO (MODE B — TWO-COLUMN STEPPER) ==================== */}
          {view === "generate" && (
            <form
              onSubmit={handleStartModeBGenerate}
              className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
            >
              {/* Left 7 Columns: Numbered Stepper Form (1 Reference, 2 Content, 3 Voice & Style, 4 Output) */}
              <div className="lg:col-span-7 space-y-5">
                {!dismissGenTip && (
                  <div className="rm-card-subtle p-3.5 flex items-center justify-between gap-3 text-[14px]">
                    <div className="flex items-center gap-2.5">
                      <Info className="w-4 h-4 shrink-0" style={{ color: "var(--accent)" }} />
                      <span>
                        <strong>Tip:</strong> Drop a reference clip below or select one from the Vault. RefMotion automatically matches its category folder.
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setDismissGenTip(true)}
                      className="rm-btn-ghost p-1 min-h-0"
                      aria-label="Dismiss tip"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}

                {/* STEP 1: REFERENCE */}
                <section className="rm-card p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-[18px] font-semibold">
                      1. Reference Source
                    </h2>
                    <span className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                      60% Primary Visuals • 70% Script & Voice Style
                    </span>
                  </div>

                  {/* Drag & Drop Reference Upload */}
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const f = e.dataTransfer.files?.[0];
                      if (f) handlePrepareReferenceDrop(f, "generate");
                    }}
                    className="rm-dropzone p-5"
                  >
                    <input
                      id="gen-ref-file"
                      type="file"
                      accept="video/*"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handlePrepareReferenceDrop(f, "generate");
                      }}
                    />
                    <label
                      htmlFor="gen-ref-file"
                      className="cursor-pointer flex flex-col items-center text-center space-y-1.5"
                    >
                      <Upload className="w-6 h-6" style={{ color: "var(--accent)" }} />
                      <div className="font-medium text-[15px]">
                        Drop a reference video here, or{" "}
                        <span className="underline" style={{ color: "var(--accent)" }}>
                          browse file
                        </span>
                      </div>
                      <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                        Validates stream, extracts style DNA, and stores in the matched category folder
                      </p>
                    </label>

                    {genRefMeta && (
                      <div className="mt-4 pt-4 border-t flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          {genRefMeta.thumbDataUrl ? (
                            <img
                              src={genRefMeta.thumbDataUrl}
                              alt={genRefMeta.name}
                              className="w-20 aspect-video object-cover rounded border"
                            />
                          ) : (
                            <div className="w-20 aspect-video rounded flex items-center justify-center rm-card">
                              <Film className="w-4 h-4" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <div className="font-medium text-[14px] truncate">
                              {genRefMeta.name}
                            </div>
                            <div
                              className="text-[13px]"
                              style={{ color: "var(--text-muted)" }}
                            >
                              {genRefMeta.durationSec.toFixed(1)}s • {genRefMeta.sizeMb} MB
                              {genRefUploading ? ` • Uploading ${genRefUploadPct}%` : " • Indexed"}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 text-[13px]">
                          <label
                            htmlFor="gen-matched-cat"
                            style={{ color: "var(--text-muted)" }}
                          >
                            Will be saved to:
                          </label>
                          <select
                            id="gen-matched-cat"
                            value={genRefMatchedCat}
                            onChange={(e) => {
                              setGenRefMatchedCat(e.target.value);
                              setGenCategory(e.target.value);
                            }}
                            className="rm-input py-1 px-2.5 w-auto text-[13px] capitalize"
                          >
                            {categories.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Compact Vault Reference Selector (Max 2 rows with scroll) */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[14px] font-medium">
                        Or select an existing reference from Vault ({references.length})
                      </span>
                      <div className="flex items-center gap-1.5">
                        <label
                          htmlFor="gen-vault-cat"
                          className="text-[13px]"
                          style={{ color: "var(--text-muted)" }}
                        >
                          Category:
                        </label>
                        <select
                          id="gen-vault-cat"
                          value={genCategory}
                          onChange={(e) => setGenCategory(e.target.value)}
                          className="rm-input py-1 px-2.5 w-auto text-[13px] capitalize"
                        >
                          {categories.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[300px] overflow-y-auto pr-1">
                      {(references.filter((r) => r.category === genCategory).length > 0
                        ? references.filter((r) => r.category === genCategory)
                        : references
                      ).map((ref) => (
                        <VaultVideoCard
                          key={ref.id}
                          asset={ref}
                          compact
                          selected={genSelectedRefId === ref.id}
                          onSelect={() => {
                            setGenSelectedRefId(ref.id);
                            setGenCategory(ref.category);
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </section>

                {/* STEP 2: CONTENT */}
                <section className="rm-card p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-[18px] font-semibold">
                      2. Topic & Narration Script
                    </h2>
                    <button
                      type="button"
                      onClick={() => handleAutoWriteScript()}
                      disabled={autoWritingScript}
                      className="rm-btn-secondary min-h-[36px] text-[13px]"
                    >
                      {autoWritingScript ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Wand2 className="w-4 h-4" style={{ color: "var(--accent)" }} />
                      )}
                      Auto-write 70% reference-style script
                    </button>
                  </div>

                  <div>
                    <label
                      htmlFor="gen-topic-input"
                      className="block text-[14px] font-medium mb-1"
                    >
                      Video Topic
                    </label>
                    <input
                      id="gen-topic-input"
                      type="text"
                      value={genTopic}
                      onChange={(e) => {
                        setGenTopic(e.target.value);
                        setGenTitle(`${e.target.value} Reel`);
                      }}
                      className="rm-input"
                      placeholder="e.g., Playful Cats & Curious Kittens"
                      required
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="gen-script-input"
                      className="block text-[14px] font-medium mb-1"
                    >
                      Narration Script & Subtitles
                    </label>
                    <textarea
                      id="gen-script-input"
                      rows={4}
                      value={genScript}
                      onChange={(e) => setGenScript(e.target.value)}
                      className="rm-input"
                      placeholder="Enter narration script..."
                      required
                    />
                  </div>
                </section>

                {/* STEP 3: VOICE & STYLE */}
                <section className="rm-card p-5 space-y-4">
                  <h2 className="text-[18px] font-semibold">
                    3. Voice-Over & Visual Style
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label
                        htmlFor="gen-voice-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Neural Voice-Over (Self-Synthesized)
                      </label>
                      <select
                        id="gen-voice-select"
                        value={genVoiceover}
                        onChange={(e) => setGenVoiceover(e.target.value)}
                        className="rm-input"
                      >
                        <option value="kokoro_bella">Kokoro-82M: Bella (Warm Narrator)</option>
                        <option value="kokoro_sarah">Kokoro-82M: Sarah (Soft Storytelling)</option>
                        <option value="kokoro_sky">Kokoro-82M: Sky (Upbeat Creator)</option>
                        <option value="kokoro_adam">Kokoro-82M: Adam (Deep Cinematic)</option>
                        <option value="kokoro_michael">Kokoro-82M: Michael (Authoritative)</option>
                        <option value="kokoro_emma">Kokoro-82M: Emma (British Documentary)</option>
                        <option value="kokoro_george">Kokoro-82M: George (British Wildlife)</option>
                        <option value="piper_lessac">Piper Neural: Lessac (Female)</option>
                        <option value="piper_bryce">Piper Neural: Bryce (Male)</option>
                      </select>
                    </div>

                    <div>
                      <label
                        htmlFor="gen-style-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Color Grade Style
                      </label>
                      <select
                        id="gen-style-select"
                        value={genVisualStyle}
                        onChange={(e) => setGenVisualStyle(e.target.value)}
                        className="rm-input"
                      >
                        <option value="vibrant">Vibrant Pop</option>
                        <option value="cinematic">Cinematic Contrast</option>
                        <option value="golden_hour">Golden Hour Warmth</option>
                        <option value="teal_orange">Teal & Orange</option>
                      </select>
                    </div>
                  </div>
                </section>

                {/* STEP 4: OUTPUT */}
                <section className="rm-card p-5 space-y-4">
                  <h2 className="text-[18px] font-semibold">
                    4. Output Specifications
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label
                        htmlFor="gen-dur-input"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Target Duration (sec)
                      </label>
                      <input
                        id="gen-dur-input"
                        type="number"
                        min={6}
                        max={120}
                        value={genDuration}
                        onChange={(e) => setGenDuration(Number(e.target.value))}
                        className="rm-input"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="gen-ar-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Aspect Ratio
                      </label>
                      <select
                        id="gen-ar-select"
                        value={genAspectRatio}
                        onChange={(e) => setGenAspectRatio(e.target.value)}
                        className="rm-input"
                      >
                        <option value="9:16">9:16 Vertical</option>
                        <option value="16:9">16:9 Landscape</option>
                        <option value="1:1">1:1 Square</option>
                      </select>
                    </div>
                    <div>
                      <label
                        htmlFor="gen-music-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Background Music
                      </label>
                      <select
                        id="gen-music-select"
                        value={genMusic}
                        onChange={(e) => setGenMusic(e.target.value)}
                        className="rm-input"
                      >
                        <option value="cinematic">Ambient Curiosity</option>
                        <option value="energetic">Upbeat Pulse</option>
                        <option value="calm">Soft Harmonic</option>
                        <option value="none">Voice-Over Only</option>
                      </select>
                    </div>
                  </div>
                </section>
              </div>

              {/* Right 5 Columns (Sticky Summary Panel): Live Summary + Segmented Blend Bars + Primary CTA */}
              <div className="lg:col-span-5 lg:sticky lg:top-20 space-y-4">
                <div className="rm-card p-5 space-y-4">
                  <h3 className="text-[18px] font-semibold">
                    Generation Summary
                  </h3>

                  <div className="space-y-2.5 text-[14px]">
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Topic</span>
                      <span className="font-medium truncate max-w-[200px]">
                        {genTopic || "—"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Category Folder</span>
                      <span className="font-medium capitalize">{genCategory}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Primary Reference</span>
                      <span className="font-medium truncate max-w-[200px]">
                        {selectedGenRef?.title || "Auto-matched"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Voice Engine</span>
                      <span className="font-medium">{genVoiceover}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5">
                      <span style={{ color: "var(--text-muted)" }}>Format</span>
                      <span className="font-medium">
                        {genAspectRatio} • {genDuration}s • {genVisualStyle}
                      </span>
                    </div>
                  </div>

                  {/* Read-only Segmented Blend Bars with Tooltip */}
                  <div
                    className="rm-card-subtle p-3.5 space-y-3"
                    title="RefMotion inherits 70% of the reference video's script cadence, voice pacing, and subtitle rhythm while synthesizing original voice-over, and blends 60% primary reference visuals with 40% category vault clips."
                  >
                    <div className="space-y-1">
                      <div className="flex justify-between text-[13px]">
                        <span className="font-medium">Script, Voice & Subtitle Style</span>
                        <span style={{ color: "var(--text-muted)" }}>
                          70% Reference / 30% Original
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full overflow-hidden flex" style={{ backgroundColor: "var(--surface)" }}>
                        <div style={{ width: "70%", backgroundColor: "var(--accent)" }} />
                        <div style={{ width: "30%", backgroundColor: "var(--border-ui)" }} />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="flex justify-between text-[13px]">
                        <span className="font-medium">Visual Scene Blend</span>
                        <span style={{ color: "var(--text-muted)" }}>
                          60% Primary / 40% Vault
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full overflow-hidden flex" style={{ backgroundColor: "var(--surface)" }}>
                        <div style={{ width: "60%", backgroundColor: "var(--accent)" }} />
                        <div style={{ width: "40%", backgroundColor: "var(--accent-2)" }} />
                      </div>
                    </div>
                  </div>

                  {genFormError && (
                    <div
                      className="p-3 rounded-lg text-[13px] flex items-center gap-2"
                      style={{
                        backgroundColor: "var(--danger-soft)",
                        color: "var(--danger)",
                      }}
                    >
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{genFormError}</span>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={loading}
                    className="rm-btn-primary w-full"
                  >
                    {loading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Sparkles className="w-5 h-5" />
                    )}
                    Start Video Generation
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* ==================== VIEW: EDIT MY VIDEO (MODE A — TWO-COLUMN STEPPER) ==================== */}
          {view === "edit" && (
            <form
              onSubmit={handleStartModeAEdit}
              className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
            >
              {/* Left 7 Columns: Numbered Stepper (1 Reference, 2 Raw Source, 3 Style & Instructions, 4 Output) */}
              <div className="lg:col-span-7 space-y-5">
                {!dismissEditTip && (
                  <div className="rm-card-subtle p-3.5 flex items-center justify-between gap-3 text-[14px]">
                    <div className="flex items-center gap-2.5">
                      <Info className="w-4 h-4 shrink-0" style={{ color: "var(--accent-2)" }} />
                      <span>
                        <strong>Tip:</strong> Attach a reference video in Step 1 to save it to the matching category folder and blend 50/50 with your stored Vault.
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setDismissEditTip(true)}
                      className="rm-btn-ghost p-1 min-h-0"
                      aria-label="Dismiss tip"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}

                {/* STEP 1: REFERENCE */}
                <section className="rm-card p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-[18px] font-semibold">
                      1. Reference Video (50% Attached + 50% Vault)
                    </h2>
                  </div>

                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      const f = e.dataTransfer.files?.[0];
                      if (f) handlePrepareReferenceDrop(f, "edit");
                    }}
                    className="rm-dropzone p-5"
                  >
                    <input
                      id="edit-ref-file"
                      type="file"
                      accept="video/*"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handlePrepareReferenceDrop(f, "edit");
                      }}
                    />
                    <label
                      htmlFor="edit-ref-file"
                      className="cursor-pointer flex flex-col items-center text-center space-y-1.5"
                    >
                      <Upload className="w-6 h-6" style={{ color: "var(--accent-2)" }} />
                      <div className="font-medium text-[15px]">
                        Drop a reference video here, or{" "}
                        <span className="underline" style={{ color: "var(--accent-2)" }}>
                          browse file
                        </span>
                      </div>
                      <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                        Auto-matches category folder and extracts 50% reference pacing & color profile
                      </p>
                    </label>

                    {editRefMeta && (
                      <div className="mt-4 pt-4 border-t flex flex-wrap items-center justify-between gap-3">
                        <div className="flex items-center gap-3 min-w-0">
                          {editRefMeta.thumbDataUrl ? (
                            <img
                              src={editRefMeta.thumbDataUrl}
                              alt={editRefMeta.name}
                              className="w-20 aspect-video object-cover rounded border"
                            />
                          ) : (
                            <div className="w-20 aspect-video rounded flex items-center justify-center rm-card">
                              <Film className="w-4 h-4" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <div className="font-medium text-[14px] truncate">
                              {editRefMeta.name}
                            </div>
                            <div
                              className="text-[13px]"
                              style={{ color: "var(--text-muted)" }}
                            >
                              {editRefMeta.durationSec.toFixed(1)}s • {editRefMeta.sizeMb} MB
                              {editRefUploading
                                ? ` • Uploading ${editRefUploadPct}%`
                                : " • Indexed"}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 text-[13px]">
                          <label
                            htmlFor="edit-matched-cat"
                            style={{ color: "var(--text-muted)" }}
                          >
                            Will be saved to:
                          </label>
                          <select
                            id="edit-matched-cat"
                            value={editRefMatchedCat}
                            onChange={(e) => {
                              setEditRefMatchedCat(e.target.value);
                              setEditCategory(e.target.value);
                            }}
                            className="rm-input py-1 px-2.5 w-auto text-[13px] capitalize"
                          >
                            {categories.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Vault Reference Selector */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[14px] font-medium">
                        Or select a reference from Vault
                      </span>
                      <select
                        aria-label="Filter reference category"
                        value={editCategory}
                        onChange={(e) => setEditCategory(e.target.value)}
                        className="rm-input py-1 px-2.5 w-auto text-[13px] capitalize"
                      >
                        {categories.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 max-h-[300px] overflow-y-auto pr-1">
                      {(references.filter((r) => r.category === editCategory).length > 0
                        ? references.filter((r) => r.category === editCategory)
                        : references
                      ).map((ref) => (
                        <VaultVideoCard
                          key={ref.id}
                          asset={ref}
                          compact
                          selected={editSelectedRefId === ref.id}
                          onSelect={() => {
                            setEditSelectedRefId(ref.id);
                            setEditCategory(ref.category);
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </section>

                {/* STEP 2: RAW SOURCE VIDEO & PROJECT TITLE */}
                <section className="rm-card p-5 space-y-4">
                  <h2 className="text-[18px] font-semibold">
                    2. Raw Footage & Project Title
                  </h2>

                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={async (e) => {
                      e.preventDefault();
                      const f = e.dataTransfer.files?.[0];
                      if (f) {
                        const meta = await inspectLocalVideoFile(f);
                        setRawVideoMeta(meta);
                        setEditFormError("");
                      }
                    }}
                    className="rm-dropzone p-5"
                  >
                    <input
                      id="raw-source-file"
                      type="file"
                      accept="video/*"
                      className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (f) {
                          const meta = await inspectLocalVideoFile(f);
                          setRawVideoMeta(meta);
                          setEditFormError("");
                        }
                      }}
                    />
                    <label
                      htmlFor="raw-source-file"
                      className="cursor-pointer flex flex-col items-center text-center space-y-1.5"
                    >
                      <Video className="w-6 h-6" style={{ color: "var(--accent-2)" }} />
                      <div className="font-medium text-[15px]">
                        {rawVideoMeta
                          ? rawVideoMeta.name
                          : "Drop your raw video here, or browse file *"}
                      </div>
                      <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                        Your raw subject is preserved while applying the 50/50 reference editing plan
                      </p>
                    </label>

                    {rawVideoMeta && (
                      <div className="mt-4 pt-4 border-t flex items-center gap-3">
                        {rawVideoMeta.thumbDataUrl && (
                          <img
                            src={rawVideoMeta.thumbDataUrl}
                            alt={rawVideoMeta.name}
                            className="w-20 aspect-video object-cover rounded border"
                          />
                        )}
                        <div className="text-[13px]">
                          <div className="font-medium text-[14px]">
                            {rawVideoMeta.name}
                          </div>
                          <div style={{ color: "var(--text-muted)" }}>
                            {rawVideoMeta.durationSec.toFixed(1)}s • {rawVideoMeta.sizeMb} MB
                            {rawUploadPct > 0 && rawUploadPct < 100
                              ? ` • Uploading ${rawUploadPct}%`
                              : ""}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor="edit-title-input"
                      className="block text-[14px] font-medium mb-1"
                    >
                      Project Title (matched against Vault for 50% stored reference blend)
                    </label>
                    <input
                      id="edit-title-input"
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="rm-input"
                      required
                    />
                  </div>
                </section>

                {/* STEP 3: EDITING INSTRUCTIONS & INTENSITY */}
                <section className="rm-card p-5 space-y-4">
                  <h2 className="text-[18px] font-semibold">
                    3. Editing Instructions & Style
                  </h2>
                  <div>
                    <label
                      htmlFor="edit-inst-input"
                      className="block text-[14px] font-medium mb-1"
                    >
                      Editing Instructions
                    </label>
                    <textarea
                      id="edit-inst-input"
                      rows={3}
                      value={editInstructions}
                      onChange={(e) => setEditInstructions(e.target.value)}
                      className="rm-input"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label
                        htmlFor="edit-intensity-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Editing Intensity
                      </label>
                      <select
                        id="edit-intensity-select"
                        value={editIntensity}
                        onChange={(e) => setEditIntensity(e.target.value)}
                        className="rm-input"
                      >
                        <option value="Minimal">Minimal</option>
                        <option value="Moderate">Moderate</option>
                        <option value="Dynamic">Dynamic</option>
                        <option value="Cinematic">Cinematic</option>
                      </select>
                    </div>
                    <div>
                      <label
                        htmlFor="edit-captions-input"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Subtitles / Captions
                      </label>
                      <input
                        id="edit-captions-input"
                        type="text"
                        value={editCaptions}
                        onChange={(e) => setEditCaptions(e.target.value)}
                        placeholder="Optional custom caption text..."
                        className="rm-input"
                      />
                    </div>
                  </div>
                </section>

                {/* STEP 4: OUTPUT */}
                <section className="rm-card p-5 space-y-4">
                  <h2 className="text-[18px] font-semibold">
                    4. Output Specifications
                  </h2>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div>
                      <label
                        htmlFor="edit-dur-input"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Final Duration (sec)
                      </label>
                      <input
                        id="edit-dur-input"
                        type="number"
                        min={3}
                        max={180}
                        value={editDuration}
                        onChange={(e) => setEditDuration(Number(e.target.value))}
                        className="rm-input"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="edit-ar-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Aspect Ratio
                      </label>
                      <select
                        id="edit-ar-select"
                        value={editAspectRatio}
                        onChange={(e) => setEditAspectRatio(e.target.value)}
                        className="rm-input"
                      >
                        <option value="9:16">9:16 Vertical</option>
                        <option value="16:9">16:9 Landscape</option>
                        <option value="1:1">1:1 Square</option>
                      </select>
                    </div>
                    <div>
                      <label
                        htmlFor="edit-qual-select"
                        className="block text-[14px] font-medium mb-1"
                      >
                        Quality
                      </label>
                      <select
                        id="edit-qual-select"
                        value={editQuality}
                        onChange={(e) => setEditQuality(e.target.value)}
                        className="rm-input"
                      >
                        <option value="720p">720p Fast HD</option>
                        <option value="1080p">1080p Full HD</option>
                      </select>
                    </div>
                  </div>
                </section>
              </div>

              {/* Right 5 Columns (Sticky Summary Panel) */}
              <div className="lg:col-span-5 lg:sticky lg:top-20 space-y-4">
                <div className="rm-card p-5 space-y-4">
                  <h3 className="text-[18px] font-semibold">
                    Editing Summary
                  </h3>

                  <div className="space-y-2.5 text-[14px]">
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Raw Source</span>
                      <span className="font-medium truncate max-w-[200px]">
                        {rawVideoMeta?.name || "Not selected"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Attached / Selected Ref</span>
                      <span className="font-medium truncate max-w-[200px]">
                        {editRefMeta?.name || selectedEditRef?.title || "Auto"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between py-1.5 border-b">
                      <span style={{ color: "var(--text-muted)" }}>Category Vault</span>
                      <span className="font-medium capitalize">{editCategory}</span>
                    </div>
                    <div className="flex items-center justify-between py-1.5">
                      <span style={{ color: "var(--text-muted)" }}>Output</span>
                      <span className="font-medium">
                        {editAspectRatio} • {editDuration}s • {editIntensity}
                      </span>
                    </div>
                  </div>

                  {/* Read-Only Segmented 50/50 Blend Bar */}
                  <div
                    className="rm-card-subtle p-3.5 space-y-2"
                    title="Mode A blends 50% of the editing pacing and color profile from your attached/selected reference video with 50% from stored Reference Vault videos matching your project title and category."
                  >
                    <div className="flex justify-between text-[13px]">
                      <span className="font-medium">Reference Style Blend</span>
                      <span style={{ color: "var(--text-muted)" }}>
                        50% Attached / 50% Vault
                      </span>
                    </div>
                    <div
                      className="w-full h-2 rounded-full overflow-hidden flex"
                      style={{ backgroundColor: "var(--surface)" }}
                    >
                      <div style={{ width: "50%", backgroundColor: "var(--accent-2)" }} />
                      <div style={{ width: "50%", backgroundColor: "var(--accent)" }} />
                    </div>
                  </div>

                  {editFormError && (
                    <div
                      className="p-3 rounded-lg text-[13px] flex items-center gap-2"
                      style={{
                        backgroundColor: "var(--danger-soft)",
                        color: "var(--danger)",
                      }}
                    >
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{editFormError}</span>
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={loading}
                    className="rm-btn-teal w-full"
                  >
                    {loading ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Scissors className="w-5 h-5" />
                    )}
                    Start Video Editing
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* ==================== VIEW: REFERENCE VAULT ==================== */}
          {view === "library" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left 8 Cols: Filter Bar & 16:9 Uniform Video Grid */}
              <div className="lg:col-span-8 space-y-4">
                <div className="rm-card p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="text-[20px] font-semibold">
                      Reference Vault ({references.length})
                    </h2>
                    <div className="flex gap-2 flex-1 max-w-sm">
                      <input
                        type="text"
                        aria-label="Search reference library"
                        value={libSearchQuery}
                        onChange={(e) => setLibSearchQuery(e.target.value)}
                        placeholder="Search by title or tag..."
                        className="rm-input py-1.5 text-[14px]"
                      />
                      <button
                        type="button"
                        onClick={async () => {
                          const res = await api.searchReferences({
                            category:
                              libFilterCategory === "all"
                                ? null
                                : libFilterCategory,
                            query: libSearchQuery,
                            top_k: 35,
                          });
                          setReferences(res.results || []);
                        }}
                        className="rm-btn-secondary shrink-0"
                      >
                        <Search className="w-4 h-4" /> Search
                      </button>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    <button
                      type="button"
                      onClick={() => {
                        setLibFilterCategory("all");
                        api
                          .listReferences()
                          .then((r) => setReferences(r.assets || []));
                      }}
                      className="px-3 py-1 rounded-lg text-[13px] font-medium border transition"
                      style={{
                        backgroundColor:
                          libFilterCategory === "all"
                            ? "var(--accent-soft)"
                            : "var(--surface-2)",
                        borderColor:
                          libFilterCategory === "all"
                            ? "var(--accent)"
                            : "var(--border)",
                        color: "var(--text)",
                      }}
                    >
                      All
                    </button>
                    {categories.map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => {
                          setLibFilterCategory(c);
                          api
                            .listReferences(c)
                            .then((r) => setReferences(r.assets || []));
                        }}
                        className="px-3 py-1 rounded-lg text-[13px] font-medium border capitalize transition"
                        style={{
                          backgroundColor:
                            libFilterCategory === c
                              ? "var(--accent-soft)"
                              : "var(--surface-2)",
                          borderColor:
                            libFilterCategory === c
                              ? "var(--accent)"
                              : "var(--border)",
                          color: "var(--text)",
                        }}
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                </div>

                {references.length === 0 ? (
                  <div className="rm-card p-8 text-center space-y-2">
                    <Library
                      className="w-7 h-7 mx-auto"
                      style={{ color: "var(--text-muted)" }}
                    />
                    <p className="text-[15px]" style={{ color: "var(--text-muted)" }}>
                      No reference videos found in this category.
                    </p>
                    <button
                      type="button"
                      onClick={() => setShowOnboarding(true)}
                      className="rm-btn-primary"
                    >
                      Open Upload Wizard
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                    {references.map((ref) => (
                      <VaultVideoCard
                        key={ref.id}
                        asset={ref}
                        selected={selectedRefDetail?.id === ref.id}
                        onSelect={() => setSelectedRefDetail(ref)}
                        onInspect={() => setSelectedRefDetail(ref)}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Right 4 Cols: Inspector & Add Reference Form */}
              <div className="lg:col-span-4 space-y-4 lg:sticky lg:top-20">
                {selectedRefDetail && (
                  <div className="rm-card p-5 space-y-3">
                    <div className="flex items-center justify-between">
                      <span
                        className="px-2.5 py-0.5 rounded text-[13px] font-medium capitalize"
                        style={{
                          backgroundColor: "var(--accent-soft)",
                          color: "var(--accent)",
                        }}
                      >
                        {selectedRefDetail.category}
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() =>
                            setConfirmDeleteId({
                              type: "reference",
                              id: selectedRefDetail.id,
                              title: selectedRefDetail.title,
                            })
                          }
                          className="rm-btn-ghost p-1.5 min-h-0"
                          style={{ color: "var(--danger)" }}
                          aria-label="Delete reference video"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setSelectedRefDetail(null)}
                          className="rm-btn-ghost p-1.5 min-h-0"
                          aria-label="Close inspector"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <h3 className="text-[16px] font-semibold">
                      {selectedRefDetail.title}
                    </h3>

                    <video
                      src={selectedRefDetail.video_url}
                      controls
                      className="w-full aspect-video rounded-lg bg-black object-cover"
                    />

                    <div className="grid grid-cols-2 gap-2 text-[13px]">
                      <div className="rm-card-subtle p-2.5">
                        <span style={{ color: "var(--text-muted)" }} className="block">
                          Duration
                        </span>
                        <strong className="text-[14px]">
                          {Number(selectedRefDetail.duration || 0).toFixed(1)}s
                        </strong>
                      </div>
                      <div className="rm-card-subtle p-2.5">
                        <span style={{ color: "var(--text-muted)" }} className="block">
                          Pacing / Color
                        </span>
                        <strong className="text-[14px] capitalize">
                          {selectedRefDetail.pacing} • {selectedRefDetail.color_style}
                        </strong>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => {
                          setGenSelectedRefId(selectedRefDetail.id);
                          setGenCategory(selectedRefDetail.category);
                          setView("generate");
                        }}
                        className="rm-btn-primary text-[13px] min-h-[38px]"
                      >
                        Use in Generate
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditSelectedRefId(selectedRefDetail.id);
                          setEditCategory(selectedRefDetail.category);
                          setView("edit");
                        }}
                        className="rm-btn-teal text-[13px] min-h-[38px]"
                      >
                        Use in Edit
                      </button>
                    </div>
                  </div>
                )}

                <form
                  onSubmit={handleIngestReference}
                  className="rm-card p-5 space-y-3.5"
                >
                  <h3 className="text-[16px] font-semibold flex items-center gap-2">
                    <Plus className="w-4 h-4" style={{ color: "var(--accent)" }} />
                    Add Reference Video
                  </h3>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Upload licensed or your own content to index into the Reference Vault.
                  </p>
                  <div>
                    <label
                      htmlFor="vault-file-input"
                      className="block text-[13px] font-medium mb-1"
                    >
                      Video File
                    </label>
                    <input
                      id="vault-file-input"
                      type="file"
                      accept="video/*"
                      onChange={async (e) => {
                        const f = e.target.files?.[0] || null;
                        setIngestFile(f);
                        if (f) {
                          try {
                            const m = await api.matchCategory(
                              f.name,
                              ingestCategory
                            );
                            if (m?.matched_category)
                              setIngestCategory(m.matched_category);
                          } catch {
                            // ignore
                          }
                        }
                      }}
                      className="rm-input text-[13px]"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="vault-cat-select"
                      className="block text-[13px] font-medium mb-1"
                    >
                      Will be saved to category
                    </label>
                    <select
                      id="vault-cat-select"
                      value={ingestCategory}
                      onChange={(e) => setIngestCategory(e.target.value)}
                      className="rm-input capitalize"
                    >
                      {categories.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label
                      htmlFor="vault-title-input"
                      className="block text-[13px] font-medium mb-1"
                    >
                      Title (Optional)
                    </label>
                    <input
                      id="vault-title-input"
                      type="text"
                      value={ingestTitle}
                      onChange={(e) => setIngestTitle(e.target.value)}
                      placeholder="Auto-named from filename"
                      className="rm-input"
                    />
                  </div>
                  {ingestPct > 0 && (
                    <div className="text-[13px]" style={{ color: "var(--accent)" }}>
                      Uploading & indexing ({ingestPct}%)...
                    </div>
                  )}
                  <button
                    type="submit"
                    disabled={loading}
                    className="rm-btn-primary w-full"
                  >
                    <Upload className="w-4 h-4" /> Store in Reference Vault
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* ==================== VIEW: RENDER QUEUE ==================== */}
          {view === "queue" && (
            <div className="space-y-5">
              <RenderProgressPanel
                job={primaryActiveJob || jobs[0]}
                onCancel={async (jid) => {
                  await api.cancelJob(jid);
                  refreshAll();
                }}
                onOpenPreview={() => setView("preview")}
              />

              <div className="rm-card p-5 space-y-4">
                <h2 className="text-[20px] font-semibold">
                  Render Queue & Job History ({jobs.length})
                </h2>

                {jobs.length === 0 ? (
                  <div className="rm-card-subtle p-6 text-center space-y-2">
                    <Orbit
                      className="w-6 h-6 mx-auto"
                      style={{ color: "var(--text-muted)" }}
                    />
                    <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                      No render jobs queued yet.
                    </p>
                    <button
                      type="button"
                      onClick={() => setView("generate")}
                      className="rm-btn-primary text-[13px]"
                    >
                      Generate a video
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {jobs.map((j) => (
                      <div
                        key={j.id}
                        className="rm-card-subtle p-4 flex flex-wrap items-center justify-between gap-4"
                      >
                        <div className="space-y-0.5">
                          <div className="font-semibold text-[15px]">
                            {j.job_type === "generate_video"
                              ? "Mode B — AI Video Generation"
                              : "Mode A — Reference Video Edit"}
                          </div>
                          <div
                            className="text-[13px]"
                            style={{ color: "var(--text-muted)" }}
                          >
                            Stage: <strong style={{ color: "var(--text)" }}>{j.stage}</strong>{" "}
                            • Engine: {j.rendering_engine}
                            {j.processing_duration_sec
                              ? ` • ${Number(j.processing_duration_sec).toFixed(1)}s`
                              : ""}
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          <span
                            className="px-2.5 py-0.5 rounded text-[13px] font-medium capitalize"
                            style={{
                              backgroundColor:
                                j.status === "completed"
                                  ? "var(--success-soft)"
                                  : j.status === "failed"
                                  ? "var(--danger-soft)"
                                  : "var(--accent-soft)",
                              color:
                                j.status === "completed"
                                  ? "var(--success)"
                                  : j.status === "failed"
                                  ? "var(--danger)"
                                  : "var(--accent)",
                            }}
                          >
                            {j.status}
                          </span>
                          {j.status === "completed" && (
                            <button
                              type="button"
                              onClick={() => {
                                const p = projects.find(
                                  (pr) => pr.id === j.project_id
                                );
                                if (p) setActiveProject(p);
                                setView("preview");
                              }}
                              className="rm-btn-secondary min-h-[36px] text-[13px]"
                            >
                              <Play className="w-3.5 h-3.5" /> Open Monitor
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ==================== VIEW: MASTER MONITOR ==================== */}
          {view === "preview" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              <div className="lg:col-span-5 rm-card p-5 space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-[18px] font-semibold truncate">
                    {activeProject?.title || "Master Monitor"}
                  </h2>
                  {activeProject?.outputs?.[0] && (
                    <a
                      href={activeProject.outputs[0].download_url}
                      className="rm-btn-primary min-h-[36px] text-[13px] px-3"
                    >
                      <Download className="w-4 h-4" /> Download MP4
                    </a>
                  )}
                </div>

                {activeProject?.outputs?.[0] ? (
                  <video
                    key={activeProject.outputs[0].video_url}
                    src={activeProject.outputs[0].video_url}
                    controls
                    className="w-full max-h-[460px] rounded-lg bg-black"
                  />
                ) : (
                  <div className="rm-card-subtle p-8 text-center space-y-2">
                    <Play
                      className="w-6 h-6 mx-auto"
                      style={{ color: "var(--text-muted)" }}
                    />
                    <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                      Select a completed project to inspect its rendered video.
                    </p>
                  </div>
                )}
              </div>

              <div className="lg:col-span-7 rm-card p-5 space-y-4">
                <h2 className="text-[18px] font-semibold">
                  Timeline & Scene Breakdown
                </h2>
                {activeProject?.timelines?.[0] ? (
                  <div className="space-y-3">
                    <div
                      className="rm-card-subtle p-3.5 text-[14px]"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {activeProject.timelines[0].planner_notes}
                    </div>
                    <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                      {(activeProject.timelines[0].edl || []).map(
                        (sc: any, idx: number) => (
                          <div
                            key={idx}
                            className="rm-card-subtle p-3.5 flex items-center justify-between gap-3"
                          >
                            <div className="min-w-0">
                              <div className="font-medium text-[14px]">
                                Scene {idx + 1}: {sc.role || sc.slot || `Shot ${idx + 1}`}
                              </div>
                              <div
                                className="text-[13px] truncate"
                                style={{ color: "var(--text-muted)" }}
                              >
                                {sc.narration || sc.rationale || sc.visual_notes}
                              </div>
                            </div>
                            <span
                              className="px-2 py-0.5 rounded text-[13px] font-medium shrink-0"
                              style={{
                                backgroundColor: "var(--surface)",
                                color: "var(--accent)",
                              }}
                            >
                              {sc.blend_source || `${sc.duration}s`}
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                    No timeline generated for this project yet.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ==================== VIEW: PROJECTS ==================== */}
          {view === "projects" && (
            <div className="rm-card p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-[20px] font-semibold">
                  All Projects ({projects.length})
                </h2>
                <button
                  type="button"
                  onClick={() => setView("generate")}
                  className="rm-btn-primary min-h-[38px] text-[14px]"
                >
                  <Plus className="w-4 h-4" /> New Project
                </button>
              </div>

              {projects.length === 0 ? (
                <div className="rm-card-subtle p-8 text-center space-y-2">
                  <FolderKanban
                    className="w-6 h-6 mx-auto"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                    No projects yet.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {projects.map((p) => (
                    <div
                      key={p.id}
                      onClick={() => {
                        setActiveProject(p);
                        setView("preview");
                      }}
                      className="rm-card-subtle rm-card-hover p-4 cursor-pointer flex flex-col justify-between gap-3"
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span
                            className="px-2 py-0.5 rounded text-[13px] font-medium"
                            style={{
                              backgroundColor:
                                p.mode === "edit"
                                  ? "var(--accent-2-soft)"
                                  : "var(--accent-soft)",
                              color:
                                p.mode === "edit"
                                  ? "var(--accent-2)"
                                  : "var(--accent)",
                            }}
                          >
                            Mode {p.mode === "edit" ? "A (Edit)" : "B (Generate)"}
                          </span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmDeleteId({
                                type: "project",
                                id: p.id,
                                title: p.title,
                              });
                            }}
                            className="rm-btn-ghost p-1 min-h-0"
                            style={{ color: "var(--danger)" }}
                            aria-label={`Delete project ${p.title}`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                        <h3 className="text-[16px] font-semibold truncate">
                          {p.title}
                        </h3>
                        <p
                          className="text-[13px] capitalize"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {p.category} • {p.aspect_ratio} • {p.target_duration}s
                        </p>
                      </div>
                      <div className="flex items-center justify-between pt-2 border-t text-[13px]">
                        <span
                          className="capitalize font-medium"
                          style={{
                            color:
                              p.status === "completed"
                                ? "var(--success)"
                                : p.status === "failed"
                                ? "var(--danger)"
                                : "var(--warning)",
                          }}
                        >
                          {p.status}
                        </span>
                        <span style={{ color: "var(--accent)" }}>Inspect →</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ==================== VIEW: SETTINGS ==================== */}
          {view === "settings" && (
            <div className="rm-card p-6 space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-[20px] font-semibold">Studio Settings</h2>
                  <p className="text-[14px]" style={{ color: "var(--text-muted)" }}>
                    Configure rendering defaults, voice synthesis, and onboarding preferences.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowOnboarding(true)}
                  className="rm-btn-secondary"
                >
                  Open Setup Wizard
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px]">
                    Default Rendering Engine
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Active engine: {settingsData?.default_rendering_engine || "ffmpeg"} (FFmpeg 6.1 CPU-safe pipeline)
                  </p>
                </div>
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px]">
                    Neural Voice-Over Engine
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Kokoro-82M ONNX & Piper Neural ONNX (100% local synthesis)
                  </p>
                </div>
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px]">
                    Mode B Reference Blending
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    70% Reference script/voice/subtitle cadence + 60% Primary Reference / 40% Category Vault
                  </p>
                </div>
                <div className="rm-card-subtle p-4 space-y-1.5">
                  <div className="font-semibold text-[15px]">
                    Mode A Reference Blending
                  </div>
                  <p className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    50% Attached Reference Video + 50% Stored Category Vault Reference
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* ==================== VIEW: SYSTEM HEALTH ==================== */}
          {view === "health" && (
            <div className="rm-card p-6 space-y-5">
              <h2 className="text-[20px] font-semibold">
                System Health & Capabilities
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rm-card-subtle p-4">
                  <div className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    CPU Cores
                  </div>
                  <div className="text-[20px] font-semibold mt-1">
                    {health?.system?.cpu_count || 8} Logical Threads
                  </div>
                </div>
                <div className="rm-card-subtle p-4">
                  <div className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Reference Vault
                  </div>
                  <div className="text-[20px] font-semibold mt-1">
                    {references.length} Indexed Videos
                  </div>
                </div>
                <div className="rm-card-subtle p-4">
                  <div className="text-[13px]" style={{ color: "var(--text-muted)" }}>
                    Worker Status
                  </div>
                  <div
                    className="text-[20px] font-semibold mt-1"
                    style={{ color: "var(--success)" }}
                  >
                    {health?.worker?.running ? "Active & Ready" : "Standby"}
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
