export type NavPage =
  | 'dashboard'
  | 'create'
  | 'edit'
  | 'generate'
  | 'library'
  | 'projects'
  | 'queue'
  | 'preview'
  | 'settings'
  | 'health';

export interface ReferenceScene {
  id: string;
  scene_index: number;
  start_time: number;
  end_time: number;
  duration: number;
  representative_frame_url?: string;
  shot_composition?: string;
  motion_level?: string;
  dominant_color?: string;
}

export interface ReferenceAsset {
  id: string;
  original_filename: string;
  title: string;
  description: string;
  category: string;
  subcategory?: string;
  tags: string[];
  sha256: string;
  perceptual_hash?: string;
  duration: number;
  width: number;
  height: number;
  resolution: string;
  fps: number;
  aspect_ratio: string;
  bitrate?: number;
  video_codec?: string;
  audio_codec?: string;
  has_audio: boolean;
  video_url: string;
  thumbnail_url?: string;
  contact_sheet_url?: string;
  analysis_status: string;
  source_info: string;
  license_info: string;
  usage_count: number;
  created_at?: string;
  style_profile?: any;
  pacing: string;
  average_shot_duration: number;
  color_style: string;
  motion_intensity: string;
  zoom_effects: boolean;
  scenes: ReferenceScene[];
  relevance_score?: number;
}

export interface ProjectFileItem {
  id: string;
  file_role: string;
  original_filename: string;
  file_size_bytes: number;
  duration?: number;
  width?: number;
  height?: number;
  resolution?: string;
  fps?: number;
  aspect_ratio?: string;
  video_codec?: string;
  audio_codec?: string;
  has_audio: boolean;
  video_url: string;
  thumbnail_url?: string;
  created_at?: string;
}

export interface RenderOutputItem {
  id: string;
  timeline_id?: string;
  job_id?: string;
  output_type: string;
  rendering_engine: string;
  video_url: string;
  download_url: string;
  preview_url: string;
  thumbnail_url?: string;
  file_size_bytes: number;
  duration: number;
  width: number;
  height: number;
  resolution: string;
  fps: number;
  video_codec?: string;
  audio_codec?: string;
  is_valid: boolean;
  created_at?: string;
}

export interface TimelineItem {
  id: string;
  version: number;
  duration: number;
  aspect_ratio: string;
  resolution: string;
  fps: number;
  edl: any[];
  timeline: any;
  planner_notes?: string;
  created_at?: string;
}

export interface Project {
  id: string;
  title: string;
  mode: 'edit' | 'generate';
  category: string;
  target_duration: number;
  aspect_ratio: string;
  target_platform: string;
  instructions?: string;
  topic?: string;
  script_text?: string;
  visual_style: string;
  target_audience?: string;
  captions_enabled: boolean;
  caption_text?: string;
  music_preference: string;
  voiceover_preference: string;
  language: string;
  video_quality: string;
  editing_intensity: string;
  selected_reference_id?: string;
  selected_reference?: ReferenceAsset;
  status: string;
  is_private: boolean;
  allow_library_promotion: boolean;
  source_analysis?: any;
  files: ProjectFileItem[];
  timelines: TimelineItem[];
  outputs: RenderOutputItem[];
  jobs: any[];
  created_at?: string;
  updated_at?: string;
}

export interface JobEventItem {
  id: string;
  stage: string;
  status: string;
  message: string;
  progress_percent: number;
  created_at?: string;
}

export interface JobItem {
  id: string;
  project_id?: string;
  project_title?: string;
  job_type: string;
  status: string;
  stage: string;
  progress_percent: number;
  rendering_engine: string;
  retry_count: number;
  max_retries: number;
  cancel_requested: boolean;
  payload?: any;
  result?: any;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  processing_duration_sec?: number;
  created_at?: string;
  events: JobEventItem[];
}

export interface GenerationTemplate {
  id: string;
  name: string;
  category: string;
  description: string;
  aspect_ratio: string;
  default_duration: number;
  visual_style: string;
  structure: any[];
}
