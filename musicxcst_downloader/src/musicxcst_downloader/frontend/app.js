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
};

const $ = (id) => document.getElementById(id);
const elements = {};
const views = {
  navButtons: [],
  pages: new Map(),
};

const formatOptions = [
  ["mp3", "MP3 audio"],
  ["ogg", "OGG audio"],
  ["wav", "WAV audio"],
  ["flac", "FLAC audio"],
  ["m4a", "M4A/AAC audio"],
];

const qualityOptions = [
  ["audio-best", "Best audio"],
  ["audio-small", "Audio small file"],
];

const audioFormats = new Set(formatOptions.map(([value]) => value));
const audioQualities = new Set(qualityOptions.map(([value]) => value));
const historyRenderLimit = 80;

function normalizeFormat(value) {
  return audioFormats.has(value) ? value : "mp3";
}

function normalizeQuality(value) {
  return audioQualities.has(value) ? value : "audio-best";
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

function setStatus(text, detail = "--") {
  elements.statusText.textContent = text;
  elements.speedEta.textContent = detail;
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
  $("filenameInput").value = data.suggested_filename || `${data.safe_filename || "download"}.${extensionForFormat()}`;
  $("longWarning").classList.toggle("hidden", !data.long_warning);
  $("thumb").classList.toggle("empty", !data.thumbnail);
  $("thumb").innerHTML = data.thumbnail ? `<img src="${data.thumbnail}" alt="">` : "No thumbnail";
  $("formatsList").innerHTML = (data.available_formats || []).slice(0, 32).map((f) => {
    const rate = f.tbr ? `${Math.round(f.tbr)}k` : "";
    const sampleRate = f.asr ? `${f.asr} Hz` : "";
    const atmos = f.dolby_atmos ? " | Dolby Atmos" : "";
    return `<div>${f.format_id || "--"} | ${f.ext || "--"} | ${f.acodec || "no audio"}${atmos} ${rate} ${sampleRate}</div>`;
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
  if (item?.output_path) await api().open_folder(item.output_path);
}

async function removeHistory(index) {
  renderHistory(await api().remove_history(index));
}

function fillSettings(settings) {
  state.settings = settings;
  const defaultFormat = normalizeFormat(settings.default_format);
  const defaultQuality = normalizeQuality(settings.default_quality);
  $("folderInput").value = settings.default_output_folder || "";
  $("setOutput").value = settings.default_output_folder || "";
  $("formatSelect").value = defaultFormat;
  $("qualitySelect").value = defaultQuality;
  $("setFormat").value = defaultFormat;
  $("setQuality").value = defaultQuality;
  $("setAccent").value = settings.accent_color || "#56f0ff";
  applyAccentColor(settings.accent_color);
  $("setFfmpegMode").value = settings.ffmpeg_mode || "system";
  $("setFfmpegPath").value = settings.custom_ffmpeg_path || "";
  $("setMaxDuration").value = settings.max_duration_warning_minutes || 60;
  $("setOpenAfter").checked = Boolean(settings.open_folder_after_download);
  $("setLogging").value = settings.logging_level || "INFO";
}

function setupSettingsSelects() {
  fillOptions($("formatSelect"), formatOptions);
  fillOptions($("qualitySelect"), qualityOptions);
  fillOptions($("setFormat"), formatOptions);
  fillOptions($("setQuality"), qualityOptions);
}

async function saveSettingsPatch(patch) {
  state.settingsSaving = true;
  markSettingsSaving();
  try {
    fillSettings(await api().save_settings(patch));
    markSettingsSaved();
    return true;
  } catch (error) {
    state.settingsDirty = true;
    const indicator = $("settingsSaveState");
    if (indicator) indicator.textContent = "Save failed";
    setStatus(`Settings save failed: ${error.message || error}`);
    return false;
  } finally {
    state.settingsSaving = false;
  }
}

function collectSettingsPatch() {
  return {
    default_output_folder: $("setOutput").value,
    default_format: $("setFormat").value,
    default_quality: $("setQuality").value,
    accent_color: $("setAccent").value,
    ffmpeg_mode: $("setFfmpegMode").value,
    custom_ffmpeg_path: $("setFfmpegPath").value,
    max_duration_warning_minutes: Number($("setMaxDuration").value || 60),
    open_folder_after_download: $("setOpenAfter").checked,
    logging_level: $("setLogging").value,
  };
}

function markSettingsDirty() {
  state.settingsDirty = true;
  const indicator = $("settingsSaveState");
  if (indicator) indicator.textContent = "Unsaved changes";
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
      state.analyzing = true;
      setStatus(event.status);
    }
    if (event.type === "analysis") {
      state.analyzing = false;
      if (event.ok) {
        renderAnalysis(event.data);
        setStatus("Analysis complete.");
      } else {
        setStatus(`Analysis failed: ${event.error}`);
      }
    }
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
      elements.progressStage.textContent = "Complete";
      elements.progressBytes.textContent = event.output_path || "--";
    }
    if (event.type === "error") {
      state.downloading = false;
      $("downloadBtn").disabled = false;
      setStatus(`Error: ${event.message}`);
      elements.progressStage.textContent = "Error";
    }
    if (event.type === "history") {
      state.history = event.items || [];
      state.historyRendered = false;
      if (state.activePage === "history") renderHistory();
    }
    if (event.type === "settings") {
      fillSettings(event.settings || {});
      markSettingsSaved();
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
  const boot = await api().startup();
  $("legalNotice").textContent = boot.legalNotice;
  fillSettings(boot.settings);
  state.history = boot.history || [];
  if (state.activePage === "history") renderHistory();
  renderFfmpeg(boot.ffmpeg);
  $("firstRun").classList.toggle("hidden", Boolean(boot.settings.first_run_confirmed));
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

  previousButton?.classList.remove("active");
  previousPage?.classList.remove("active");
  previousPage?.setAttribute("hidden", "");
  nextButton?.classList.add("active");
  nextPage?.removeAttribute("hidden");
  nextPage?.classList.add("active");
  state.activePage = pageName;

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
    await saveSettingsPatch({ first_run_confirmed: true });
    $("firstRun").classList.add("hidden");
  });

  $("analyzeBtn").addEventListener("click", async () => {
    setProgress(0);
    setStatus("Starting analysis...");
    const result = await api().analyze($("urlInput").value.trim());
    if (!result.ok) setStatus(result.error);
  });

  $("formatSelect").addEventListener("change", () => {
    $("formatSelect").value = normalizeFormat($("formatSelect").value);
    ensureFilenameExtension();
  });

  $("folderBtn").addEventListener("click", async () => {
    const folder = await api().choose_output_folder();
    if (folder) $("folderInput").value = folder;
  });

  async function performDownload(overwrite = false) {
    ensureFilenameExtension();
    $("downloadBtn").disabled = true;
    setProgress(0, { status: "Starting download...", stage: "Starting", detail: "--" });
    const result = await api().download({
      url: $("urlInput").value.trim(),
      format: $("formatSelect").value,
      quality: $("qualitySelect").value,
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

  $("cancelBtn").addEventListener("click", async () => {
    const result = await api().cancel_download();
    if (!result.ok) setStatus(result.error);
  });

  $("copyPathBtn").addEventListener("click", () => copyText($("outputPath").value));
  $("openCurrentFolder").addEventListener("click", () => api().open_folder($("outputPath").value || $("folderInput").value));
  $("clearHistoryBtn").addEventListener("click", async () => renderHistory(await api().clear_history()));
  elements.historyList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-history-action]");
    if (!button) return;
    const index = Number(button.dataset.historyIndex);
    const item = state.history[index];
    if (!item) return;
    if (button.dataset.historyAction === "open") await api().open_folder(item.output_path);
    if (button.dataset.historyAction === "copy") await copyText(item.output_path);
    if (button.dataset.historyAction === "remove") renderHistory(await api().remove_history(index));
  });
  document.querySelectorAll("[data-external-url]").forEach((link) => {
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      const result = await api().open_external_url(event.currentTarget.dataset.externalUrl);
      if (!result.ok) setStatus(`Could not open link: ${result.error}`);
    });
  });

  ["setOutput", "setFormat", "setQuality", "setAccent", "setFfmpegMode", "setFfmpegPath", "setMaxDuration", "setLogging"].forEach((id) => {
    $(id).addEventListener("change", () => {
      markSettingsDirty();
      scheduleSettingsSave();
    });
  });
  $("setAccent").addEventListener("input", (event) => {
    applyAccentColor(event.target.value);
    markSettingsDirty();
    scheduleSettingsSave();
  });
  $("setOpenAfter").addEventListener("change", () => {
    markSettingsDirty();
    scheduleSettingsSave();
  });

  $("selectFfmpegBtn").addEventListener("click", async () => {
    const path = await api().select_ffmpeg();
    if (path) {
      $("setFfmpegPath").value = path;
      markSettingsDirty();
      scheduleSettingsSave();
    }
  });

  $("settingsSaveBtn").addEventListener("click", async () => {
    clearTimeout(state.settingsSaveTimer);
    await saveSettingsPatch(collectSettingsPatch());
    setStatus("Settings saved.");
  });
  $("downloadFfmpegBtn").addEventListener("click", async () => {
    clearTimeout(state.settingsSaveTimer);
    if (state.settingsDirty) await saveSettingsPatch(collectSettingsPatch());
    setFfmpegDownloadState(true, "Starting...");
    const result = await api().download_managed_ffmpeg();
    if (!result.ok) {
      setFfmpegDownloadState(false);
      setStatus(result.error);
    } else {
      setStatus(result.status);
    }
  });
  $("testFfmpegBtn").addEventListener("click", async () => renderFfmpeg(await api().test_ffmpeg($("setFfmpegMode").value, $("setFfmpegPath").value)));
  $("resetSettingsBtn").addEventListener("click", async () => {
    fillSettings(await api().reset_settings());
    markSettingsSaved();
    setStatus("Settings reset.");
  });

  document.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.key.toLowerCase() === "l") {
      event.preventDefault();
      $("urlInput").focus();
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
  });

  init();
});
