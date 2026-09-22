const api = () => window.pywebview.api;

const state = {
  settings: {},
  history: [],
  lastOutputPath: "",
  analyzing: false,
  downloading: false,
  settingsDirty: false,
  progressFrame: 0,
  pendingProgress: null,
  pendingProgressEvent: null,
  activePage: "download",
  historyRendered: false,
  historyRenderFrame: 0,
  settingsSaveTimer: 0,
  settingsSaving: false,
  settingsEditVersion: 0,
  browserOpen: false,
  updateAvailable: false,
  currentVersion: "unknown",
  currentYtdlpVersion: "unknown",
};

let initStarted = false;

const $ = (id) => document.getElementById(id);
const elements = {};
const views = {
  navButtons: [],
  pages: new Map(),
};

const modeOptions = [
  ["audio", "Audio only"],
  ["video", "Video only"],
  ["video-audio", "Video + audio"],
];

const audioFormatOptions = [
  ["mp3", "MP3 audio"],
  ["ogg", "OGG audio"],
  ["wav", "WAV audio"],
  ["flac", "FLAC audio"],
  ["m4a", "M4A/AAC audio"],
  ["opus", "Opus audio"],
  ["aac", "AAC audio"],
  ["alac", "ALAC audio"],
];

const videoFormatOptions = [
  ["mp4", "MP4 video"],
  ["mkv", "MKV video"],
  ["webm", "WebM video"],
  ["mov", "MOV video"],
  ["avi", "AVI video"],
  ["m4v", "M4V video"],
  ["ts", "MPEG-TS video"],
];

const qualityOptions = [
  ["audio-best", "Best audio"],
  ["audio-small", "Audio small file"],
];

const videoQualityOptions = [
  ["best", "Best available"],
  ["2160", "2160p / 4K"],
  ["1440", "1440p / 2K"],
  ["1080", "1080p / Full HD"],
  ["720", "720p / HD"],
  ["480", "480p"],
  ["360", "360p"],
];

const audioFormats = new Set(audioFormatOptions.map(([value]) => value));
const videoFormats = new Set(videoFormatOptions.map(([value]) => value));
const audioQualities = new Set(qualityOptions.map(([value]) => value));
const videoQualities = new Set(videoQualityOptions.map(([value]) => value));
const historyRenderLimit = 80;

function toCamelCase(value) {
  return String(value).replace(/_([a-z])/g, (_, char) => char.toUpperCase());
}

function getApiMethod(name) {
  const bridge = api();
  if (!bridge) return null;
  if (typeof bridge[name] === "function") return bridge[name].bind(bridge);
  const camelName = toCamelCase(name);
  if (typeof bridge[camelName] === "function") return bridge[camelName].bind(bridge);
  return null;
}

async function callApi(name, ...args) {
  const method = getApiMethod(name);
  if (method) return method(...args);
  const invoke = getApiMethod("invoke");
  if (invoke) return invoke(name, args);
  throw new Error(`API method '${name}' is not available. Reinstall the current app build.`);
}

function normalizeFormat(value) {
  return audioFormats.has(value) || videoFormats.has(value) ? value : "mp3";
}

function normalizeQuality(value) {
  return audioQualities.has(value) ? value : "audio-best";
}

function normalizeMode(value) {
  return ["audio", "video", "video-audio"].includes(value) ? value : "audio";
}

function formatOptionsForMode(mode) {
  return normalizeMode(mode) === "audio" ? audioFormatOptions : videoFormatOptions;
}

function qualityOptionsForMode(mode) {
  const normalizedMode = normalizeMode(mode);
  if (normalizedMode === "audio") return qualityOptions;
  return videoQualityOptions.map(([value, label]) => [
    value,
    value === "best"
      ? (normalizedMode === "video-audio" ? "Best video + best audio" : "Best video")
      : label,
  ]);
}

function refreshDownloadOptions(mode, format = "", quality = "") {
  const normalizedMode = normalizeMode(mode);
  fillOptions($("formatSelect"), formatOptionsForMode(normalizedMode));
  fillOptions($("qualitySelect"), qualityOptionsForMode(normalizedMode));
  const formats = formatOptionsForMode(normalizedMode).map(([value]) => value);
  const qualities = qualityOptionsForMode(normalizedMode).map(([value]) => value);
  $("formatSelect").value = formats.includes(format) ? format : formats[0];
  $("qualitySelect").value = qualities.includes(quality) ? quality : qualities[0];
  ensureFilenameExtension();
}

function fillOptions(select, options) {
  select.innerHTML = options.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
}

function hexToRgb(value) {
  const match = String(value || "").trim().match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!match) return [86, 240, 255];
  return [parseInt(match[1], 16), parseInt(match[2], 16), parseInt(match[3], 16)];
}

function contrastForRgb([red, green, blue]) {
  const luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255;
  return luminance > 0.58 ? "#061015" : "#ffffff";
}

function applyAccentColor(value) {
  const accent = value || "#56f0ff";
  const rgb = hexToRgb(accent);
  document.documentElement.style.setProperty("--accent", accent);
  document.documentElement.style.setProperty("--accent-rgb", rgb.join(", "));
  document.documentElement.style.setProperty("--accent-contrast", contrastForRgb(rgb));
}

function normalizeAccentColor(value) {
  const text = String(value || "").trim();
  if (!/^#?[a-f\d]{6}$/i.test(text)) return "#56f0ff";
  return text.startsWith("#") ? text : `#${text}`;
}

function describeError(error) {
  if (!error) return "Unknown error";
  if (typeof error === "string") return error;
  try {
    if (typeof error.message === "string" && error.message.trim()) return error.message;
  } catch (_) {
    return "Unexpected bridge error";
  }
  return "Unexpected bridge error";
}

function describeAnalysisError(error) {
  const detail = describeError(error).replace(/^ERROR:\s*/i, "").replace(/\s+/g, " ").trim();
  const cases = [
    {
      match: /video is (not )?available|video is unavailable|private video/i,
      summary: "This video cannot be accessed.",
      guidance: "Check that the URL is correct and that the video is public, still online, and available in your region.",
    },
    {
      match: /age-restricted|confirm your age|inappropriate for certain audiences/i,
      summary: "This video is age-restricted.",
      guidance: "YouTube requires an authenticated, age-verified account. Try another accessible video.",
    },
    {
      match: /not available in your country|geo.?restrict|country restriction|地域制限/i,
      summary: "This video is region-restricted.",
      guidance: "The uploader or YouTube blocks it in this region. Try a different link that is available here.",
    },
    {
      match: /sign in to confirm|login required|authentication required|members.?only|private/i,
      summary: "This video requires sign-in or membership.",
      guidance: "MusicXCST cannot access this protected content without an authenticated session. Try a public link.",
    },
    {
      match: /captcha|bot|automated|too many requests|rate.?limit/i,
      summary: "YouTube temporarily blocked the request.",
      guidance: "Wait a few minutes, avoid repeated retries, and try again with a normal public link.",
    },
    {
      match: /timed? ?out|connection reset|connection refused|name resolution|network is unreachable|temporary failure/i,
      summary: "The network request failed.",
      guidance: "Check your internet connection, firewall, VPN, and proxy settings, then retry.",
    },
    {
      match: /cookie|database is locked|could not find.*database/i,
      summary: "Browser cookies could not be read.",
      guidance: "Close every browser window, make sure YouTube is signed in in at least one detected browser, then retry. Auto mode will test every detected profile.",
    },
    {
      match: /unsupported URL|no suitable extractor|not a valid URL/i,
      summary: "This link format is not supported.",
      guidance: "Paste the full YouTube, YouTube Music, or supported provider URL instead of a search page or shortened text.",
    },
    {
      match: /ffmpeg|ffprobe/i,
      summary: "Media processing support is missing.",
      guidance: "Install or update FFmpeg from Settings before converting or merging this media.",
    },
  ];
  const matched = cases.find((item) => item.match.test(detail));
  if (matched) return { ...matched, detail };
  return {
    summary: "The link could not be analyzed.",
    guidance: "Check the URL and try again. If it still fails, review the technical details in the operation log.",
    detail,
  };
}

function setStatus(text, detail = "--") {
  elements.statusText.textContent = text;
  elements.speedEta.textContent = detail;
}

function appendTerminal(line) {
  const output = $("terminalOutput");
  if (!output) return;
  const current = output.textContent === "Ready." ? [] : output.textContent.split("\n");
  current.push(`[${new Date().toLocaleTimeString()}] ${line}`);
  output.textContent = current.slice(-120).join("\n");
  output.scrollTop = output.scrollHeight;
}

function setProgress(percent, event = null) {
  const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
  state.pendingProgress = safePercent;
  if (event) state.pendingProgressEvent = event;
  if (state.progressFrame) return;
  state.progressFrame = requestAnimationFrame(() => {
    elements.progressBar.style.width = `${state.pendingProgress}%`;
    elements.progressPercent.textContent = `${Math.round(state.pendingProgress)}%`;
    if (state.pendingProgressEvent) {
      const progress = state.pendingProgressEvent;
      const detail = [progress.speed, progress.eta && `ETA ${progress.eta}`].filter(Boolean).join(" / ") || "--";
      setStatus(progress.status || "Downloading...", detail);
      elements.progressStage.textContent = progress.stage || progress.status || "Working";
      elements.progressBytes.textContent = progress.detail || "--";
      state.pendingProgressEvent = null;
    }
    state.progressFrame = 0;
  });
}

function setAnalysisState(active, { ok = null, detail = "" } = {}) {
  state.analyzing = active;
  const button = $("analyzeBtn");
  const workflowStatus = $("workflowStatus");
  const workflowStatusText = $("workflowStatusText");
  const workflowPanel = document.querySelector(".workflow-panel");
  if (!button || !workflowStatus || !workflowStatusText) return;

  button.disabled = active;
  button.classList.toggle("is-analyzing", active);
  button.setAttribute("aria-busy", active ? "true" : "false");
  button.setAttribute("aria-label", active ? "Analyzing link" : "Analyze link");
  button.replaceChildren();
  const content = document.createElement("span");
  content.className = "analyze-btn-content";
  if (active) {
    const spinner = document.createElement("span");
    spinner.className = "analyze-spinner";
    spinner.setAttribute("aria-hidden", "true");
    content.append(spinner, document.createTextNode("Analyzing…"));
  } else {
    content.textContent = "Analyze Link";
  }
  button.append(content);

  workflowStatus.classList.toggle("is-analyzing", active);
  workflowPanel?.classList.toggle("analysis-active", active);
  if (active) {
    workflowStatusText.textContent = "Analyzing";
    setProgress(0);
    elements.progressPercent.textContent = "…";
    elements.progressStage.textContent = "Analyzing";
    elements.progressBytes.textContent = detail || "Scanning streams…";
    return;
  }

  workflowStatusText.textContent = ok === false ? "Error" : "Ready";
  if (ok === true) {
    setProgress(100);
    elements.progressPercent.textContent = "100%";
    elements.progressStage.textContent = "Analysis complete";
    elements.progressBytes.textContent = detail || "Streams scanned";
  } else if (ok === false) {
    setProgress(0);
    elements.progressPercent.textContent = "0%";
    elements.progressStage.textContent = "Analysis failed";
    elements.progressBytes.textContent = detail || "--";
  }
}

function extensionForFormat() {
  return $("formatSelect").value === "m4a" ? "m4a" : $("formatSelect").value;
}

function ensureFilenameExtension() {
  const ext = extensionForFormat();
  let name = $("filenameInput").value.trim() || `download.${ext}`;
  name = name.replace(/\.[a-z0-9]{2,5}$/i, "");
  $("filenameInput").value = `${name}.${ext}`;
}

function renderAnalysis(data) {
  $("metaTitle").textContent = data.title || "--";
  $("metaUploader").textContent = data.uploader || "--";
  $("metaDuration").textContent = data.duration || "--";
  $("metaAudio").textContent = data.best_audio_quality || "--";
  $("metaAtmos").textContent = data.dolby_atmos || "--";
  const details = [data.audio_codec, data.audio_bitrate && `${Math.round(data.audio_bitrate)} kbps`, data.audio_sample_rate && `${data.audio_sample_rate} Hz`, data.audio_channels && `${data.audio_channels} ch`].filter(Boolean);
  $("metaAudioDetails").textContent = details.join(" / ") || "--";
  $("metaAudioSize").textContent = data.best_audio_filesize || "Unknown";
  $("metaVideo").textContent = data.best_video_quality || "--";
  const videoDetails = [data.best_video_codec, data.best_video_fps && `${data.best_video_fps} fps`, data.best_video_bitrate && `${Math.round(data.best_video_bitrate)} kbps`].filter(Boolean);
  $("metaVideoDetails").textContent = videoDetails.join(" / ") || "--";
  $("metaVideoSize").textContent = data.best_video_size || "Unknown";
  $("metaFormats").textContent = `${data.formats_count || 0} total / ${data.video_formats_count || 0} video / ${data.audio_formats_count || 0} audio`;
  $("scanSummary").textContent = `Best available: ${data.best_video_quality || "no video"} video and ${data.best_audio_quality || "no audio"}.`;
  $("filenameInput").value = data.suggested_filename || `${data.safe_filename || "download"}.${extensionForFormat()}`;
  $("longWarning").classList.toggle("hidden", !data.long_warning);
  $("thumb").classList.toggle("empty", !data.thumbnail);
  $("thumb").replaceChildren();
  if (data.thumbnail) {
    const image = document.createElement("img");
    image.alt = "Cover artwork";
    image.loading = "lazy";
    image.decoding = "async";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => {
      $("thumb").classList.add("empty");
      $("thumb").textContent = "Artwork unavailable";
    }, { once: true });
    image.src = data.thumbnail;
    $("thumb").append(image);
  } else {
    $("thumb").textContent = "No thumbnail";
  }
  $("formatsList").innerHTML = (data.available_formats || []).slice(0, 40).map((f) => {
    const rate = f.tbr ? `${Math.round(f.tbr)}k` : "";
    const sampleRate = f.asr ? `${f.asr} Hz` : "";
    const atmos = f.dolby_atmos ? " | Dolby Atmos" : "";
    const resolution = f.height ? `${f.width || "?"}x${f.height}${f.fps ? ` ${f.fps}fps` : ""}` : "audio";
    return `<div>${f.kind || "stream"} | ${f.format_id || "--"} | ${f.ext || "--"} | ${resolution} | ${f.vcodec || "no video"} | ${f.acodec || "no audio"}${atmos} ${rate} ${sampleRate}</div>`;
  }).join("") || "No formats returned.";
}

function renderHistory(items = state.history) {
  state.history = items || [];
  state.historyRendered = true;
  const visibleItems = state.history.slice(0, historyRenderLimit);
  const extraCount = Math.max(0, state.history.length - visibleItems.length);
  $("historyList").innerHTML = visibleItems.length ? `
    ${visibleItems.map((item, index) => `
    <article class="history-item">
      <div>
        <strong>${escapeHtml(item.title || "Untitled")}</strong>
        <span>${escapeHtml(item.status || "")} / ${escapeHtml(item.selected_format || "")} / ${escapeHtml(item.date_time || "")}</span>
        <span>${escapeHtml(item.output_path || "")}</span>
      </div>
      <div class="history-actions">
        <button class="ghost" data-history-action="open" data-history-index="${index}">Open</button>
        <button class="ghost" data-history-action="copy" data-history-index="${index}">Copy</button>
        <button class="ghost danger" data-history-action="remove" data-history-index="${index}">Remove</button>
      </div>
    </article>
    `).join("")}
    ${extraCount ? `<p class="lead">Showing latest ${historyRenderLimit} of ${state.history.length} downloads.</p>` : ""}
  ` : `<p class="lead">No downloads yet.</p>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

async function copyText(text) {
  await navigator.clipboard.writeText(text || state.lastOutputPath || "");
  setStatus("Path copied.");
}

async function openHistory(index) {
  const item = state.history[index];
  if (item?.output_path) await callApi("open_folder", item.output_path);
}

async function removeHistory(index) {
  renderHistory(await callApi("remove_history", index));
}

function fillSettings(settings, { updateSettingsForm = true } = {}) {
  state.settings = settings;
  applyUiTheme(settings.ui_theme, settings.motion_enabled);
  const defaultMode = normalizeMode(settings.default_mode);
  const defaultFormat = normalizeFormat(settings.default_format);
  const defaultQuality = defaultMode === "audio" ? normalizeQuality(settings.default_quality) : (videoQualities.has(settings.default_video_quality) ? settings.default_video_quality : "best");
  $("folderInput").value = settings.default_output_folder || "";
  $("modeSelect").value = defaultMode;
  refreshDownloadOptions(defaultMode, defaultFormat, defaultQuality);
  applyAccentColor(settings.accent_color);
  if (!updateSettingsForm) return;
  $("setOutput").value = settings.default_output_folder || "";
  $("setMode").value = defaultMode;
  fillOptions($("setFormat"), formatOptionsForMode(defaultMode));
  fillOptions($("setQuality"), qualityOptions);
  fillOptions($("setVideoQuality"), videoQualityOptions);
  $("setFormat").value = defaultFormat;
  $("setQuality").value = defaultMode === "audio" ? normalizeQuality(settings.default_quality) : "audio-best";
  $("setVideoQuality").value = settings.default_video_quality || "best";
  $("setTheme").value = settings.ui_theme === "aurora" ? "aurora" : "classic";
  $("setMotion").checked = settings.motion_enabled !== false;
  $("setShowStartScreen").checked = settings.show_start_screen !== false;
  $("setUseBrowserCookies").checked = settings.use_browser_cookies !== false;
  $("setBrowserCookieSource").value = settings.browser_cookie_source || "auto";
  $("cookieFileStatus").textContent = settings.cookie_file_path ? `Imported: ${settings.cookie_file_path}` : "No cookie file imported";
  $("setAccent").value = settings.accent_color || "#56f0ff";
  $("setFfmpegMode").value = settings.ffmpeg_mode || "system";
  $("setFfmpegPath").value = settings.custom_ffmpeg_path || "";
  $("setMaxDuration").value = settings.max_duration_warning_minutes || 60;
  $("setOpenAfter").checked = Boolean(settings.open_folder_after_download);
  $("setLogging").value = settings.logging_level || "INFO";
}

function setupSettingsSelects() {
  fillOptions($("modeSelect"), modeOptions);
  fillOptions($("formatSelect"), audioFormatOptions);
  fillOptions($("qualitySelect"), qualityOptions);
  fillOptions($("setMode"), modeOptions);
  fillOptions($("setFormat"), audioFormatOptions);
  fillOptions($("setQuality"), qualityOptions);
  fillOptions($("setVideoQuality"), videoQualityOptions);
}

async function saveSettingsPatch(patch) {
  const saveVersion = state.settingsEditVersion;
  state.settingsSaving = true;
  markSettingsSaving();
  try {
    const savedSettings = await callApi("save_settings", patch);
    const hasNewerEdits = state.settingsEditVersion !== saveVersion;
    fillSettings(savedSettings, { updateSettingsForm: !hasNewerEdits });
    if (hasNewerEdits) {
      markSettingsDirty(false);
    } else {
      markSettingsSaved();
    }
    return true;
  } catch (error) {
    markSettingsDirty(false, "Save failed");
    setStatus(`Settings save failed: ${describeError(error)}`);
    return false;
  } finally {
    state.settingsSaving = false;
    if (state.settingsDirty) scheduleSettingsSave();
  }
}

function collectSettingsPatch() {
  return {
    default_output_folder: $("setOutput").value,
    default_mode: $("setMode").value,
    default_format: $("setFormat").value,
    default_quality: $("setQuality").value,
    default_video_quality: $("setVideoQuality").value,
    ui_theme: $("setTheme").value,
    motion_enabled: $("setMotion").checked,
    show_start_screen: $("setShowStartScreen").checked,
    use_browser_cookies: $("setUseBrowserCookies").checked,
    browser_cookie_source: $("setBrowserCookieSource").value,
    accent_color: normalizeAccentColor($("setAccent").value),
    ffmpeg_mode: $("setFfmpegMode").value,
    custom_ffmpeg_path: $("setFfmpegPath").value,
    max_duration_warning_minutes: Number($("setMaxDuration").value || 60),
    open_folder_after_download: $("setOpenAfter").checked,
    logging_level: $("setLogging").value,
  };
}

function markSettingsDirty(incrementVersion = true, label = "Unsaved changes") {
  if (incrementVersion) state.settingsEditVersion += 1;
  state.settingsDirty = true;
  const indicator = $("settingsSaveState");
  if (indicator) indicator.textContent = label;
}

function applyUiTheme(theme = "classic", motionEnabled = true) {
  document.documentElement.dataset.theme = theme === "aurora" ? "aurora" : "classic";
  document.documentElement.classList.toggle("motion-disabled", motionEnabled === false);
}

function markSettingsSaving() {
  const indicator = $("settingsSaveState");
  if (indicator) indicator.textContent = "Saving...";
}

function markSettingsSaved() {
  state.settingsDirty = false;
  const indicator = $("settingsSaveState");
  if (indicator) indicator.textContent = "Saved";
}

function scheduleSettingsSave() {
  clearTimeout(state.settingsSaveTimer);
  state.settingsSaveTimer = setTimeout(() => {
    if (state.settingsDirty && !state.settingsSaving) {
      saveSettingsPatch(collectSettingsPatch());
    }
  }, 700);
}

async function flushSettingsSave() {
  clearTimeout(state.settingsSaveTimer);
  let attempts = 0;
  while (state.settingsSaving && attempts < 100) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    attempts += 1;
  }
  if (state.settingsDirty) return saveSettingsPatch(collectSettingsPatch());
  return true;
}

function browserBounds() {
  const viewport = $("webViewport");
  if (!viewport) return null;
  const rect = viewport.getBoundingClientRect();
  return {
    x: Math.round(rect.left),
    y: Math.round(rect.top),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
  };
}

async function syncBrowserLayout() {
  const visible = state.activePage === "web";
  const bounds = browserBounds();
  if (!bounds) return;
  try {
    await callApi("browser_layout", bounds, visible);
  } catch (error) {
    if (visible) setStatus(`Browser layout failed: ${describeError(error)}`);
  }
}

function queueHistoryRender() {
  if (state.historyRendered || state.historyRenderFrame) return;
  state.historyRenderFrame = requestAnimationFrame(() => {
    state.historyRenderFrame = 0;
    if (state.activePage === "history") renderHistory();
  });
}

window.MusicXCST = {
  receiveEvent(event) {
    if (event.type === "analyze_status") {
      setAnalysisState(true, { detail: event.status || "Scanning streams…" });
      setStatus(event.status);
    }
    if (event.type === "analysis") {
      const analysisError = event.ok ? null : describeAnalysisError(event.error);
      const scanDetail = event.ok ? `${event.data.formats_count || 0} streams scanned` : analysisError.summary;
      setAnalysisState(false, { ok: event.ok, detail: scanDetail });
      if (event.ok) {
        renderAnalysis(event.data);
        appendTerminal(`Analysis complete: ${event.data.formats_count || 0} streams scanned.`);
        setStatus("Analysis complete.");
      } else {
        appendTerminal(`Analysis failed: ${analysisError.summary}`);
        appendTerminal(`What to do: ${analysisError.guidance}`);
        appendTerminal(`Technical details: ${analysisError.detail}`);
        setStatus(analysisError.summary, "See operation log for details");
      }
    }
    if (event.type === "terminal") appendTerminal(event.line || event.status || "Working...");
    if (event.type === "status") setStatus(event.status);
    if (event.type === "progress") {
      state.downloading = true;
      $("downloadBtn").disabled = true;
      setProgress(event.percent, event);
    }
    if (event.type === "complete") {
      state.downloading = false;
      state.lastOutputPath = event.output_path || "";
      $("outputPath").value = state.lastOutputPath;
      $("downloadBtn").disabled = false;
      setProgress(100);
      setStatus("Download complete.");
      appendTerminal(`Completed: ${event.output_path || "output file"}`);
      elements.progressStage.textContent = "Complete";
      elements.progressBytes.textContent = event.output_path || "--";
    }
    if (event.type === "error") {
      state.downloading = false;
      $("downloadBtn").disabled = false;
      setStatus(`Error: ${event.message}`);
      appendTerminal(`ERROR: ${event.message}`);
      elements.progressStage.textContent = "Error";
    }
    if (event.type === "history") {
      state.history = event.items || [];
      state.historyRendered = false;
      if (state.activePage === "history") renderHistory();
    }
    if (event.type === "settings") {
      const settings = event.settings || {};
      const preserveForm = state.activePage === "settings" && (state.settingsDirty || state.settingsSaving);
      fillSettings(settings, { updateSettingsForm: !preserveForm });
      if (!preserveForm) markSettingsSaved();
    }
    if (event.type === "ytdlp_update") {
      const updateAvailable = event.available !== false;
      setYtdlpUpdateState(Boolean(event.running), event.running ? "Updating..." : (updateAvailable ? "Update yt-dlp" : "yt-dlp up to date"), updateAvailable);
      if (event.percent !== undefined) setYtdlpProgress(event.percent, event.status || "Updating yt-dlp...");
      else if (event.running) setYtdlpProgress(0, event.status || "Updating yt-dlp...");
      else if (event.ok) setYtdlpProgress(100, event.status || "yt-dlp update finished.");
      else setYtdlpProgress(0, event.status || "yt-dlp update failed.");
      if (event.current_version || event.latest_version) {
        renderYtdlp(event);
      } else if (event.version) {
        renderYtdlp({ version: event.version });
      }
      if (!event.current_version && !event.latest_version && !event.version && !event.running) {
        $("ytdlpProgressStatus").textContent = event.status || "yt-dlp update check failed.";
      }
      if (event.restart) {
        setYtdlpProgress(100, "Restarting the app...");
        setStatus("Restarting the app to activate yt-dlp...");
      }
      setStatus(event.status || "yt-dlp update finished.");
      appendTerminal(event.status || "yt-dlp update finished.");
    }
    if (event.type === "app_update") {
      setAppUpdateState(Boolean(event.running), event.running ? "Updating..." : (event.available === false ? "Check for updates" : "Update App"), true);
      if (event.available !== undefined) setUpdateReminder(Boolean(event.available), event.version);
      if (event.current_version || event.version) {
        const current = event.current_version || state.currentVersion || "unknown";
        const latest = event.version || current;
        $("appUpdateStatus").textContent = event.available
          ? `Current version: ${current} • Update available: ${latest}`
          : `Current version: ${current} (up to date)`;
      } else if (event.status) {
        $("appUpdateStatus").textContent = event.status;
      }
      setStatus(event.status || "Application update finished.");
      appendTerminal(event.status || "Application update finished.");
    }
    if (event.type === "browser_status") {
      const webState = $("webState");
      state.browserOpen = Boolean(event.open);
      webState.textContent = event.error || (event.loading ? "Loading..." : event.open ? "Ready" : "Browser closed");
      webState.classList.toggle("online", Boolean(event.open));
      if (event.url) $("webAddress").value = event.url;
      $("webBackBtn").disabled = event.canBack === false;
      $("webForwardBtn").disabled = event.canForward === false;
    }
    if (event.type === "browser_send_download") {
      $("urlInput").value = event.url || "";
      switchPage("download");
      $("urlInput").focus();
      setStatus("Link copied from Web. Ready to analyze.");
    }
    if (event.type === "ffmpeg") {
      renderFfmpeg(event.status);
    }
    if (event.type === "ffmpeg_download") {
      if (event.ok === false) {
        setFfmpegDownloadState(false);
        setStatus(`FFmpeg download failed: ${event.status}`);
        return;
      }
      const percent = Number(event.percent || 0);
      setFfmpegDownloadState(percent < 100, percent < 100 ? `Downloading ${Math.round(percent)}%` : "Download App FFmpeg");
      setStatus(event.status || "Downloading FFmpeg...");
    }
  },
};

async function init() {
  setupSettingsSelects();
  const boot = await callApi("startup");
  $("legalNotice").textContent = boot.legalNotice;
  fillSettings(boot.settings);
  state.history = boot.history || [];
  if (state.activePage === "history") renderHistory();
  renderFfmpeg(boot.ffmpeg);
  renderYtdlp(boot.ytdlp);
  renderAppVersion(boot.appVersion);
  // The legal start screen is intentionally shown on every application launch.
  // It is dismissed for this session only when the user acknowledges it.
  $("firstRun").classList.toggle("hidden", boot.settings.show_start_screen === false);
  setYtdlpUpdateState(true, "Checking...");
  setAppUpdateState(true, "Checking...");
  callApi("check_app_update").catch(() => {
    setYtdlpUpdateState(false, "Update yt-dlp", true);
    setAppUpdateState(false, "Check for updates", true);
  });
}

function startInitialization() {
  if (initStarted) return;
  if (!getApiMethod("startup") && !getApiMethod("invoke")) return;
  initStarted = true;
  init().catch((error) => {
    const message = describeError(error);
    renderAppVersion("unknown");
    renderYtdlp({ version: "unknown" });
    setYtdlpUpdateState(false, "Retry yt-dlp check", true);
    setAppUpdateState(false, "Retry app check", true);
    setStatus("Could not connect to the app bridge.", message);
    appendTerminal(`Startup failed: ${message}`);
  });
}

function renderFfmpeg(info) {
  $("ffmpegMini").textContent = info.ready ? "FFmpeg ready" : "FFmpeg missing";
  $("ffmpegStatus").textContent = `ffmpeg: ${info.ffmpeg_version}\n${info.ffmpeg_path || "No path"}\n\nffprobe: ${info.ffprobe_version}\n${info.ffprobe_path || "No path"}`;
}

function setFfmpegDownloadState(running, label = "Download App FFmpeg") {
  const button = $("downloadFfmpegBtn");
  button.disabled = running;
  button.textContent = label;
}

function renderYtdlp(info) {
  const current = info?.current_version || info?.version || "unknown";
  const latest = info?.latest_version;
  state.currentYtdlpVersion = current;
  $("ytdlpStatus").textContent = latest
    ? (info.available === false ? `Installed: ${current} (up to date)` : `Installed: ${current} • Latest: ${latest}`)
    : `Installed version: ${current}`;
}

function setYtdlpUpdateState(running, label = "Update yt-dlp", enabled = true) {
  const button = $("updateYtdlpBtn");
  button.disabled = running || !enabled;
  button.textContent = label;
}

function setYtdlpProgress(percent, status = "Ready.") {
  const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
  const bar = $("ytdlpProgressBar");
  if (bar) bar.style.width = `${safePercent}%`;
  const percentLabel = $("ytdlpProgressPercent");
  if (percentLabel) percentLabel.textContent = `${Math.round(safePercent)}%`;
  const statusLabel = $("ytdlpProgressStatus");
  if (statusLabel) statusLabel.textContent = status;
}

function renderAppVersion(version) {
  state.currentVersion = version || "unknown";
  $("appUpdateStatus").textContent = `Current version: ${version || "unknown"}`;
  $("appVersionBadge").textContent = version || "unknown";
}

function setAppUpdateState(running, label = "Update App", enabled = true) {
  const button = $("updateAppBtn");
  button.disabled = running || !enabled;
  button.textContent = label;
}

function setUpdateReminder(available, version = "") {
  state.updateAvailable = available;
  const reminder = $("updateReminder");
  const reminderText = $("updateReminderText");
  reminder?.classList.toggle("hidden", !available);
  document.querySelector(".rainbow-settings")?.classList.toggle("rainbow-active", Boolean(available));
  reminderText?.classList.toggle("hidden", !available);
  if (available) {
    const label = version ? `Update ${version} available` : "A new app update is available";
    if (reminder) reminder.title = label;
    if (reminderText) reminderText.textContent = label;
  }
}

async function switchPage(pageName) {
  if (!views.pages.has(pageName) || state.activePage === pageName) return;
  if (state.activePage === "settings" && state.settingsDirty) {
    clearTimeout(state.settingsSaveTimer);
    await saveSettingsPatch(collectSettingsPatch());
  }
  const previousPage = views.pages.get(state.activePage);
  const nextPage = views.pages.get(pageName);
  const previousButton = views.navButtons.find((button) => button.dataset.page === state.activePage);
  const nextButton = views.navButtons.find((button) => button.dataset.page === pageName);
  const motionEnabled = !document.documentElement.classList.contains("motion-disabled")
    && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (motionEnabled && previousPage?.classList.contains("active")) {
    previousPage.classList.add("page-exiting");
    await new Promise((resolve) => setTimeout(resolve, 170));
  }

  previousButton?.classList.remove("active");
  previousPage?.classList.remove("active", "page-exiting");
  previousPage?.setAttribute("hidden", "");
  nextButton?.classList.add("active");
  nextPage?.removeAttribute("hidden");
  nextPage?.classList.add("active");
  if (motionEnabled) {
    nextPage?.classList.add("page-entering");
    requestAnimationFrame(() => nextPage?.classList.remove("page-entering"));
  }
  state.activePage = pageName;

  await syncBrowserLayout();

  if (pageName === "history") queueHistoryRender();
}

document.addEventListener("DOMContentLoaded", () => {
  [
    "statusText",
    "speedEta",
    "progressBar",
    "progressPercent",
    "progressStage",
    "progressBytes",
    "historyList",
  ].forEach((id) => {
    elements[id] = $(id);
  });

  views.navButtons = Array.from(document.querySelectorAll(".nav-item"));
  document.querySelectorAll(".page").forEach((page) => {
    const pageName = page.id.replace("page-", "");
    views.pages.set(pageName, page);
    if (!page.classList.contains("active")) page.setAttribute("hidden", "");
  });
  views.navButtons.forEach((button) => {
    button.addEventListener("click", () => switchPage(button.dataset.page));
  });

  $("acceptNotice").addEventListener("click", async () => {
    $("firstRun").classList.add("hidden");
  });

  $("analyzeBtn").addEventListener("click", async () => {
    const url = $("urlInput").value.trim();
    setAnalysisState(true);
    appendTerminal("$ analyze " + url);
    setStatus("Analyzing link...");
    try {
      const result = await callApi("analyze", url);
      if (!result.ok) {
        const analysisError = describeAnalysisError(result.error);
        setAnalysisState(false, { ok: false, detail: analysisError.summary });
        appendTerminal(`Analysis failed: ${analysisError.summary}`);
        appendTerminal(`What to do: ${analysisError.guidance}`);
        appendTerminal(`Technical details: ${analysisError.detail}`);
        setStatus(analysisError.summary, "See operation log for details");
      }
    } catch (error) {
      const analysisError = describeAnalysisError(error);
      setAnalysisState(false, { ok: false, detail: analysisError.summary });
      appendTerminal(`Analysis failed: ${analysisError.summary}`);
      appendTerminal(`What to do: ${analysisError.guidance}`);
      appendTerminal(`Technical details: ${analysisError.detail}`);
      setStatus(analysisError.summary, "See operation log for details");
    }
  });

  $("formatSelect").addEventListener("change", () => {
    $("formatSelect").value = normalizeFormat($("formatSelect").value);
    ensureFilenameExtension();
  });
  $("modeSelect").addEventListener("change", () => {
    refreshDownloadOptions($("modeSelect").value);
    appendTerminal(`Mode selected: ${$("modeSelect").value}`);
  });

  $("folderBtn").addEventListener("click", async () => {
    const folder = await callApi("choose_output_folder");
    if (folder) {
      $("folderInput").value = folder;
      $("setOutput").value = folder;
      await saveSettingsPatch({ default_output_folder: folder });
      setStatus("Default output folder saved.");
    }
  });

  $("setOutputBtn").addEventListener("click", async () => {
    const chooseAndSaveDefault = getApiMethod("choose_default_output_folder");
    if (chooseAndSaveDefault) {
      const result = await chooseAndSaveDefault();
      if (result?.ok) {
        fillSettings(result.settings || {}, { updateSettingsForm: true });
        markSettingsSaved();
        setStatus("Default output folder saved.");
      }
      return;
    }
    const folder = await callApi("choose_output_folder");
    if (!folder) return;
    $("setOutput").value = folder;
    $("folderInput").value = folder;
    const ok = await saveSettingsPatch({ default_output_folder: folder });
    setStatus(ok ? "Default output folder saved." : "Settings save failed.");
  });

  async function performDownload(overwrite = false) {
    ensureFilenameExtension();
    $("downloadBtn").disabled = true;
    setProgress(0, { status: "Starting download...", stage: "Starting", detail: "--" });
    const result = await callApi("download", {
      url: $("urlInput").value.trim(),
      mode: $("modeSelect").value,
      format: $("formatSelect").value,
      quality: $("qualitySelect").value,
      video_quality: $("qualitySelect").value,
      output_folder: $("folderInput").value,
      filename: $("filenameInput").value,
      legal_confirmed: $("legalCheck").checked,
      overwrite,
    });
    if (!result.ok) {
      if (String(result.error || "").includes("already exists") && confirm(`${result.error}\n\nOverwrite it?`)) {
        await performDownload(true);
        return;
      }
      $("downloadBtn").disabled = false;
      setStatus(result.error);
      elements.progressStage.textContent = "Error";
    }
  }

  $("downloadBtn").addEventListener("click", () => performDownload(false));

  const openWeb = async (value = $("webAddress").value) => {
    const result = await callApi("browser_open", value);
    if (result?.url) $("webAddress").value = result.url;
    if (!result?.ok) setStatus(result?.error || "Could not open browser.");
    await syncBrowserLayout();
  };
  $("webOpenBtn").addEventListener("click", () => openWeb());
  $("webAddress").addEventListener("keydown", (event) => {
    if (event.key === "Enter") openWeb();
  });
  $("webHomeBtn").addEventListener("click", async () => {
    const result = await callApi("browser_home");
    if (result?.url) $("webAddress").value = result.url;
  });
  $("webBackBtn").addEventListener("click", () => callApi("browser_back"));
  $("webForwardBtn").addEventListener("click", () => callApi("browser_forward"));
  $("webReloadBtn").addEventListener("click", () => callApi("browser_reload"));
  $("webStopBtn").addEventListener("click", () => callApi("browser_stop"));
  $("webYoutubeBtn").addEventListener("click", () => openWeb("https://www.youtube.com/"));
  $("webYoutubeMusicBtn").addEventListener("click", () => openWeb("https://music.youtube.com/"));
  $("webDownloadBtn").addEventListener("click", async () => {
    const result = await callApi("browser_send_current_to_download");
    if (!result?.ok) setStatus(result?.error || "Could not send this page to Download.");
  });
  $("webZoomOutBtn").addEventListener("click", async () => {
    const result = await callApi("browser_zoom", -0.1);
    if (result?.zoom) $("webZoomLabel").textContent = `${result.zoom}%`;
  });
  $("webZoomInBtn").addEventListener("click", async () => {
    const result = await callApi("browser_zoom", 0.1);
    if (result?.zoom) $("webZoomLabel").textContent = `${result.zoom}%`;
  });
  $("webFindBtn").addEventListener("click", async () => {
    const text = window.prompt("Find on this page:", "");
    if (text) await callApi("browser_find", text);
  });
  $("webCopyBtn").addEventListener("click", async () => {
    const result = await callApi("browser_copy_url");
    if (result?.url) await copyText(result.url);
  });
  $("webExternalBtn").addEventListener("click", () => callApi("browser_open_external"));

  const webResizeObserver = new ResizeObserver(() => {
    if (state.activePage === "web") syncBrowserLayout();
  });
  webResizeObserver.observe($("webViewport"));

  let browserScrollFrame = 0;
  const scheduleBrowserLayout = () => {
    if (state.activePage !== "web" || browserScrollFrame) return;
    browserScrollFrame = requestAnimationFrame(() => {
      browserScrollFrame = 0;
      syncBrowserLayout();
    });
  };
  const contentScroller = document.querySelector(".content");
  contentScroller?.addEventListener("scroll", scheduleBrowserLayout, { passive: true });
  window.addEventListener("scroll", scheduleBrowserLayout, { passive: true, capture: true });
  window.addEventListener("resize", () => {
    if (state.activePage === "web") syncBrowserLayout();
  });

  $("cancelBtn").addEventListener("click", async () => {
    const result = await callApi("cancel_download");
    if (!result.ok) setStatus(result.error);
  });

  $("copyPathBtn").addEventListener("click", () => copyText($("outputPath").value));
  $("clearTerminalBtn").addEventListener("click", () => { $("terminalOutput").textContent = "Ready."; });
  $("openCurrentFolder").addEventListener("click", () => callApi("open_folder", $("outputPath").value || $("folderInput").value));
  $("clearHistoryBtn").addEventListener("click", async () => renderHistory(await callApi("clear_history")));
  elements.historyList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-history-action]");
    if (!button) return;
    const index = Number(button.dataset.historyIndex);
    const item = state.history[index];
    if (!item) return;
    if (button.dataset.historyAction === "open") await callApi("open_folder", item.output_path);
    if (button.dataset.historyAction === "copy") await copyText(item.output_path);
    if (button.dataset.historyAction === "remove") renderHistory(await callApi("remove_history", index));
  });
  document.querySelectorAll("[data-external-url]").forEach((link) => {
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      const result = await callApi("open_external_url", event.currentTarget.dataset.externalUrl);
      if (!result.ok) setStatus(`Could not open link: ${result.error}`);
    });
  });

  ["setFormat", "setQuality", "setVideoQuality", "setFfmpegMode", "setLogging", "setTheme", "setBrowserCookieSource"].forEach((id) => {
    $(id).addEventListener("change", () => {
      if (id === "setTheme") applyUiTheme($("setTheme").value, $("setMotion").checked);
      markSettingsDirty();
      scheduleSettingsSave();
    });
  });
  $("setMotion").addEventListener("change", () => {
    applyUiTheme($("setTheme").value, $("setMotion").checked);
    markSettingsDirty();
    scheduleSettingsSave();
  });
  $("setShowStartScreen").addEventListener("change", () => {
    $("firstRun").classList.toggle("hidden", !$("setShowStartScreen").checked);
    markSettingsDirty();
    scheduleSettingsSave();
  });
  $("setUseBrowserCookies").addEventListener("change", () => {
    markSettingsDirty();
    scheduleSettingsSave();
  });
  $("importCookieFileBtn").addEventListener("click", async () => {
    const result = await callApi("select_cookie_file");
    if (result?.ok) {
      fillSettings(result.settings || {}, { updateSettingsForm: true });
      markSettingsSaved();
      setStatus("Cookie file imported locally.");
    }
  });
  $("setMode").addEventListener("change", () => {
    const mode = normalizeMode($("setMode").value);
    fillOptions($("setFormat"), formatOptionsForMode(mode));
    markSettingsDirty();
    scheduleSettingsSave();
  });
  ["setOutput", "setFfmpegPath", "setMaxDuration"].forEach((id) => {
    $(id).addEventListener("input", () => {
      markSettingsDirty();
      scheduleSettingsSave();
    });
    $(id).addEventListener("change", () => {
      markSettingsDirty();
      scheduleSettingsSave();
    });
  });
  $("setAccent").addEventListener("input", (event) => {
    applyAccentColor(event.target.value);
  });
  $("setAccent").addEventListener("change", (event) => {
    event.target.value = normalizeAccentColor(event.target.value);
    applyAccentColor(event.target.value);
    markSettingsDirty();
    scheduleSettingsSave();
  });
  $("setOpenAfter").addEventListener("change", () => {
    markSettingsDirty();
    scheduleSettingsSave();
  });

  $("selectFfmpegBtn").addEventListener("click", async () => {
    const path = await callApi("select_ffmpeg");
    if (path) {
      $("setFfmpegPath").value = path;
      markSettingsDirty();
      scheduleSettingsSave();
    }
  });

  $("settingsSaveBtn").addEventListener("click", async () => {
    clearTimeout(state.settingsSaveTimer);
    const ok = await saveSettingsPatch(collectSettingsPatch());
    setStatus(ok ? "Settings saved." : "Settings save failed.");
  });
  $("downloadFfmpegBtn").addEventListener("click", async () => {
    clearTimeout(state.settingsSaveTimer);
    if (state.settingsDirty) await saveSettingsPatch(collectSettingsPatch());
    setFfmpegDownloadState(true, "Starting...");
    const result = await callApi("download_managed_ffmpeg");
    if (!result.ok) {
      setFfmpegDownloadState(false);
      setStatus(result.error);
    } else {
      setStatus(result.status);
    }
  });
  $("updateYtdlpBtn").addEventListener("click", async () => {
    setYtdlpUpdateState(true, "Starting...");
    setYtdlpProgress(0, "Starting yt-dlp update...");
    const result = await callApi("update_ytdlp");
    if (!result.ok) {
      setYtdlpUpdateState(false);
      setYtdlpProgress(0, result.error || "yt-dlp update failed.");
      $("ytdlpStatus").textContent = result.error;
      setStatus(result.error);
    } else {
      setStatus(result.status);
    }
  });
  $("updateAppBtn").addEventListener("click", async () => {
    await flushSettingsSave();
    setAppUpdateState(true, "Checking...");
    const result = await callApi("update_app");
    if (!result.ok) {
      setAppUpdateState(false);
      $("appUpdateStatus").textContent = result.error;
      setStatus(result.error);
    } else {
      setStatus(result.status);
    }
  });
  $("testFfmpegBtn").addEventListener("click", async () => renderFfmpeg(await callApi("test_ffmpeg", $("setFfmpegMode").value, $("setFfmpegPath").value)));
  $("resetSettingsBtn").addEventListener("click", async () => {
    fillSettings(await callApi("reset_settings"));
    markSettingsSaved();
    setStatus("Settings reset.");
  });

  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key.toLowerCase() === "l") {
      event.preventDefault();
      (state.activePage === "web" ? $("webAddress") : $("urlInput")).focus();
    }
    if (state.activePage === "web" && event.ctrlKey && event.key.toLowerCase() === "r") {
      event.preventDefault();
      $("webReloadBtn").click();
    }
    if (state.activePage === "web" && event.ctrlKey && event.key.toLowerCase() === "f") {
      event.preventDefault();
      $("webFindBtn").click();
    }
    if (state.activePage === "web" && event.altKey && event.key === "ArrowLeft") {
      event.preventDefault();
      $("webBackBtn").click();
    }
    if (state.activePage === "web" && event.altKey && event.key === "ArrowRight") {
      event.preventDefault();
      $("webForwardBtn").click();
    }
    if (event.ctrlKey && event.key.toLowerCase() === "o") {
      event.preventDefault();
      $("folderBtn").click();
    }
    if (event.ctrlKey && event.key === "Enter") {
      event.preventDefault();
      (state.analyzing || $("metaTitle").textContent !== "--" ? $("downloadBtn") : $("analyzeBtn")).click();
    }
    if (event.key === "Escape" && state.downloading) $("cancelBtn").click();
    if (state.activePage === "web" && event.key === "Escape") $("webStopBtn").click();
  });

  window.addEventListener("pywebviewready", startInitialization, { once: true });
  startInitialization();
});
