const api = () => window.pywebview.api;

const state = {
  settings: {},
  history: [],
  lastOutputPath: "",
  analyzing: false,
  downloading: false,
};

const $ = (id) => document.getElementById(id);

const formatOptions = [
  ["mp4", "MP4 video"],
  ["webm", "WebM video"],
  ["mp3", "MP3 audio"],
  ["ogg", "OGG audio"],
  ["wav", "WAV audio"],
  ["flac", "FLAC audio"],
  ["m4a", "M4A/AAC audio"],
];

const qualityOptions = [
  ["best", "Best available"],
  ["1080", "1080p"],
  ["720", "720p"],
  ["480", "480p"],
  ["audio-best", "Audio only best"],
  ["audio-small", "Audio small file"],
];

function setStatus(text, detail = "--") {
  $("statusText").textContent = text;
  $("speedEta").textContent = detail;
}

function setProgress(percent) {
  $("progressBar").style.width = `${Math.max(0, Math.min(100, Number(percent) || 0))}%`;
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
  $("metaVideo").textContent = data.best_video_quality || "--";
  $("metaAudio").textContent = data.best_audio_quality || "--";
  const details = [data.audio_codec, data.audio_bitrate && `${Math.round(data.audio_bitrate)} kbps`, data.audio_sample_rate && `${data.audio_sample_rate} Hz`, data.audio_channels && `${data.audio_channels} ch`].filter(Boolean);
  $("metaAudioDetails").textContent = details.join(" / ") || "--";
  $("filenameInput").value = data.suggested_filename || `${data.safe_filename || "download"}.${extensionForFormat()}`;
  $("longWarning").classList.toggle("hidden", !data.long_warning);
  $("thumb").classList.toggle("empty", !data.thumbnail);
  $("thumb").innerHTML = data.thumbnail ? `<img src="${data.thumbnail}" alt="">` : "No thumbnail";
  $("formatsList").innerHTML = (data.available_formats || []).slice(0, 40).map((f) => {
    const rate = f.tbr ? `${Math.round(f.tbr)}k` : "";
    return `<div>${f.format_id || "--"} | ${f.ext || "--"} | ${f.resolution || "--"} | ${f.vcodec || "no video"} | ${f.acodec || "no audio"} ${rate}</div>`;
  }).join("") || "No formats returned.";
}

function renderHistory(items) {
  state.history = items || [];
  $("historyList").innerHTML = state.history.length ? state.history.map((item, index) => `
    <article class="history-item">
      <div>
        <strong>${escapeHtml(item.title || "Untitled")}</strong>
        <span>${escapeHtml(item.status || "")} / ${escapeHtml(item.selected_format || "")} / ${escapeHtml(item.date_time || "")}</span>
        <span>${escapeHtml(item.output_path || "")}</span>
      </div>
      <div class="history-actions">
        <button class="ghost" onclick="openHistory(${index})">Open</button>
        <button class="ghost" onclick="copyText('${escapeAttr(item.output_path || "")}')">Copy</button>
        <button class="ghost danger" onclick="removeHistory(${index})">Remove</button>
      </div>
    </article>
  `).join("") : `<p class="lead">No downloads yet.</p>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/\\/g, "\\\\");
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
  $("folderInput").value = settings.default_output_folder || "";
  $("setOutput").value = settings.default_output_folder || "";
  $("formatSelect").value = settings.default_format || "mp4";
  $("qualitySelect").value = settings.default_quality || "best";
  $("setFormat").value = settings.default_format || "mp4";
  $("setQuality").value = settings.default_quality || "best";
  $("setAccent").value = settings.accent_color || "#56f0ff";
  document.documentElement.style.setProperty("--accent", settings.accent_color || "#56f0ff");
  $("setFfmpegMode").value = settings.ffmpeg_mode || "system";
  $("setFfmpegPath").value = settings.custom_ffmpeg_path || "";
  $("setMaxDuration").value = settings.max_duration_warning_minutes || 60;
  $("setOpenAfter").checked = Boolean(settings.open_folder_after_download);
  $("setKeepTemp").checked = Boolean(settings.keep_temporary_original);
  $("setLogging").value = settings.logging_level || "INFO";
}

function setupSettingsSelects() {
  $("setFormat").innerHTML = formatOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
  $("setQuality").innerHTML = qualityOptions.map(([value, label]) => `<option value="${value}">${label}</option>`).join("");
}

async function saveSettingsPatch(patch) {
  fillSettings(await api().save_settings(patch));
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
    keep_temporary_original: $("setKeepTemp").checked,
    logging_level: $("setLogging").value,
  };
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
      setProgress(event.percent);
      setStatus(event.status || "Downloading...", [event.speed, event.eta && `ETA ${event.eta}`].filter(Boolean).join(" / ") || "--");
    }
    if (event.type === "complete") {
      state.downloading = false;
      state.lastOutputPath = event.output_path || "";
      $("outputPath").value = state.lastOutputPath;
      setProgress(100);
      setStatus("Download complete.");
    }
    if (event.type === "error") {
      state.downloading = false;
      setStatus(`Error: ${event.message}`);
    }
    if (event.type === "history") renderHistory(event.items);
  },
};

async function init() {
  setupSettingsSelects();
  const boot = await api().startup();
  $("legalNotice").textContent = boot.legalNotice;
  fillSettings(boot.settings);
  renderHistory(boot.history);
  renderFfmpeg(boot.ffmpeg);
  $("firstRun").classList.toggle("hidden", Boolean(boot.settings.first_run_confirmed));
}

function renderFfmpeg(info) {
  $("ffmpegMini").textContent = info.ready ? "FFmpeg ready" : "FFmpeg missing";
  $("ffmpegStatus").textContent = `ffmpeg: ${info.ffmpeg_version}\n${info.ffmpeg_path || "No path"}\n\nffprobe: ${info.ffprobe_version}\n${info.ffprobe_path || "No path"}`;
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
      button.classList.add("active");
      $(`page-${button.dataset.page}`).classList.add("active");
    });
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

  $("formatSelect").addEventListener("change", ensureFilenameExtension);

  $("folderBtn").addEventListener("click", async () => {
    const folder = await api().choose_output_folder();
    if (folder) $("folderInput").value = folder;
  });

  async function performDownload(overwrite = false) {
    ensureFilenameExtension();
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
      setStatus(result.error);
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

  ["setOutput", "setFormat", "setQuality", "setAccent", "setFfmpegMode", "setFfmpegPath", "setMaxDuration", "setLogging"].forEach((id) => {
    $(id).addEventListener("change", () => saveSettingsPatch(collectSettingsPatch()));
  });
  ["setOpenAfter", "setKeepTemp"].forEach((id) => $(id).addEventListener("change", () => saveSettingsPatch(collectSettingsPatch())));

  $("selectFfmpegBtn").addEventListener("click", async () => {
    const path = await api().select_ffmpeg();
    if (path) {
      $("setFfmpegPath").value = path;
      await saveSettingsPatch(collectSettingsPatch());
    }
  });

  $("testFfmpegBtn").addEventListener("click", async () => renderFfmpeg(await api().test_ffmpeg($("setFfmpegMode").value, $("setFfmpegPath").value)));
  $("resetSettingsBtn").addEventListener("click", async () => fillSettings(await api().reset_settings()));

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
