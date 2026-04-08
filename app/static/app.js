const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const fileList = document.getElementById("fileList");
const fileCount = document.getElementById("fileCount");
const totalSize = document.getElementById("totalSize");
const clearButton = document.getElementById("clearButton");
const processButton = document.getElementById("processButton");
const statusCard = document.getElementById("statusCard");
const statusText = document.getElementById("statusText");
const downloadLink = document.getElementById("downloadLink");
const modelName = document.getElementById("modelName");
const allowedFormats = document.getElementById("allowedFormats");
const batchLimit = document.getElementById("batchLimit");

const state = {
  files: [],
  lastDownloadUrl: null,
  maxFilesPerBatch: 50,
};

fileInput.addEventListener("change", (event) => {
  addFiles(Array.from(event.target.files || []));
  fileInput.value = "";
});

clearButton.addEventListener("click", () => {
  state.files = [];
  resetDownloadLink();
  renderFiles();
  setStatus("idle", "Daftar file dikosongkan. Siap untuk batch berikutnya.");
});

processButton.addEventListener("click", async () => {
  if (state.files.length === 0) {
    setStatus("error", "Pilih minimal satu file sebelum memulai proses.");
    return;
  }

  if (state.files.length > state.maxFilesPerBatch) {
    setStatus(
      "error",
      `Jumlah file melebihi limit batch. Maksimal ${state.maxFilesPerBatch} file sekali proses.`,
    );
    return;
  }

  const formData = new FormData();
  for (const file of state.files) {
    formData.append("files", file, file.name);
  }

  toggleBusy(true);
  resetDownloadLink();
  setStatus("processing", `Memproses ${state.files.length} file. Mohon tunggu sebentar...`);

  try {
    const response = await fetch("/remove-batch", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let message = "Terjadi kesalahan saat memproses batch.";
      try {
        const payload = await response.json();
        message = payload.detail || message;
      } catch {
        // Ignore JSON parsing errors and keep the fallback message.
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    const filename = getDownloadFilename(response.headers.get("content-disposition"));
    const url = URL.createObjectURL(blob);

    state.lastDownloadUrl = url;
    downloadLink.href = url;
    downloadLink.download = filename;
    downloadLink.classList.remove("hidden");
    setStatus("success", `Selesai. ${state.files.length} file berhasil diproses.`);
  } catch (error) {
    setStatus("error", error.message || "Terjadi kesalahan yang tidak diketahui.");
  } finally {
    toggleBusy(false);
  }
});

["dragenter", "dragover"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragover");
  });
});

dropzone.addEventListener("drop", (event) => {
  addFiles(Array.from(event.dataTransfer?.files || []));
});

window.addEventListener("beforeunload", resetDownloadLink);

void loadHealth();
renderFiles();

async function loadHealth() {
  try {
    const response = await fetch("/health");
    if (!response.ok) {
      throw new Error("Gagal mengambil status service.");
    }

    const health = await response.json();
    modelName.textContent = health.model || "Tidak diketahui";
    allowedFormats.textContent = health.allowed_extensions || "-";
    state.maxFilesPerBatch = Number(health.max_files_per_batch || 50);
    batchLimit.textContent = `${state.maxFilesPerBatch} file`;
  } catch {
    modelName.textContent = "Unavailable";
    allowedFormats.textContent = "Periksa server";
    batchLimit.textContent = "N/A";
  }
}

function addFiles(incomingFiles) {
  const deduped = new Map(
    state.files.map((file) => [buildFileKey(file), file]),
  );

  for (const file of incomingFiles) {
    const looksLikeImage =
      file.type.startsWith("image/") || /\.(avif|bmp|dib|gif|jfif|jpe|jpeg|jpg|jp2|png|tif|tiff|webp)$/i.test(file.name);
    if (!looksLikeImage) {
      continue;
    }
    deduped.set(buildFileKey(file), file);
  }

  state.files = Array.from(deduped.values());
  renderFiles();

  if (state.files.length > 0) {
    setStatus("idle", `${state.files.length} file siap diproses.`);
  }
}

function renderFiles() {
  fileCount.textContent = String(state.files.length);
  totalSize.textContent = formatBytes(
    state.files.reduce((sum, file) => sum + file.size, 0),
  );

  if (state.files.length === 0) {
    fileList.className = "file-list empty";
    fileList.innerHTML = "<p>Belum ada file yang dipilih.</p>";
    return;
  }

  fileList.className = "file-list";
  fileList.innerHTML = state.files
    .map(
      (file, index) => `
        <div class="file-item">
          <div class="file-meta">
            <p class="file-name">${escapeHtml(file.name)}</p>
            <p class="file-size">${formatBytes(file.size)}</p>
          </div>
          <button class="remove-file" type="button" data-index="${index}">Hapus</button>
        </div>
      `,
    )
    .join("");

  fileList.querySelectorAll(".remove-file").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.index);
      state.files.splice(index, 1);
      renderFiles();
      if (state.files.length === 0) {
        setStatus("idle", "Semua file dihapus dari daftar.");
      } else {
        setStatus("idle", `${state.files.length} file tersisa di daftar.`);
      }
    });
  });
}

function setStatus(kind, message) {
  statusCard.className = `status-card ${kind}`;
  statusText.textContent = message;
}

function toggleBusy(isBusy) {
  processButton.disabled = isBusy;
  clearButton.disabled = isBusy;
  processButton.textContent = isBusy ? "Sedang Memproses..." : "Proses Batch";
}

function resetDownloadLink() {
  if (state.lastDownloadUrl) {
    URL.revokeObjectURL(state.lastDownloadUrl);
    state.lastDownloadUrl = null;
  }
  downloadLink.href = "#";
  downloadLink.classList.add("hidden");
}

function buildFileKey(file) {
  return `${file.name}::${file.size}::${file.lastModified}`;
}

function formatBytes(bytes) {
  if (bytes === 0) {
    return "0 KB";
  }

  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unitIndex = 0;

  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }

  return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function getDownloadFilename(contentDisposition) {
  const fallback = "background-removed.zip";
  if (!contentDisposition) {
    return fallback;
  }

  const match = contentDisposition.match(/filename="?([^"]+)"?/i);
  return match?.[1] || fallback;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
