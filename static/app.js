const DEFAULT_PIXEL_COUNT = 25;

const state = {
  users: [],
  datasets: [],
  currentDatasetId: Number(localStorage.getItem("pixel-annotator-dataset-id")) || null,
  categories: [],
  images: [],
  detail: null,
  pixels: [],
  currentIndex: 0,
  imageElement: null,
  fitScale: 1,
  scale: 1,
  zoom: 1,
  displayWidth: 0,
  displayHeight: 0,
  editPixelsMode: false,
  pan: {
    active: false,
    moved: false,
    pointerId: null,
    startX: 0,
    startY: 0,
    scrollLeft: 0,
    scrollTop: 0,
    suppressClick: false,
  },
};

const els = {
  username: document.getElementById("usernameInput"),
  userSettings: document.getElementById("userSettingsButton"),
  userDialog: document.getElementById("userDialog"),
  userForm: document.getElementById("userForm"),
  userSelect: document.getElementById("userSelect"),
  userCreate: document.getElementById("userCreateInput"),
  userSettingsDialog: document.getElementById("userSettingsDialog"),
  userSettingsClose: document.getElementById("userSettingsCloseButton"),
  userSettingsSelect: document.getElementById("userSettingsSelect"),
  userAddForm: document.getElementById("userAddForm"),
  userAdd: document.getElementById("userAddInput"),
  userRenameForm: document.getElementById("userRenameForm"),
  userRename: document.getElementById("userRenameInput"),
  userDelete: document.getElementById("userDeleteButton"),
  connection: document.getElementById("connectionStatus"),
  uploadForm: document.getElementById("uploadForm"),
  imageInput: document.getElementById("imageInput"),
  imageName: document.getElementById("imageNameInput"),
  pixelCountInput: document.getElementById("pixelCountInput"),
  batchUpload: document.getElementById("batchUploadButton"),
  batchDialog: document.getElementById("batchUploadDialog"),
  batchForm: document.getElementById("batchUploadForm"),
  batchClose: document.getElementById("batchCloseButton"),
  batchImageInput: document.getElementById("batchImageInput"),
  batchPixelCount: document.getElementById("batchPixelCountInput"),
  imageList: document.getElementById("imageList"),
  imageCount: document.getElementById("imageCount"),
  datasetSelect: document.getElementById("datasetSelect"),
  datasetForm: document.getElementById("datasetForm"),
  datasetName: document.getElementById("datasetNameInput"),
  datasetRenameForm: document.getElementById("datasetRenameForm"),
  datasetRename: document.getElementById("datasetRenameInput"),
  datasetImageCount: document.getElementById("datasetImageCount"),
  categoryForm: document.getElementById("categoryForm"),
  categoryName: document.getElementById("categoryNameInput"),
  categoryColor: document.getElementById("categoryColorInput"),
  categoryLegend: document.getElementById("categoryLegend"),
  canvasFrame: document.getElementById("canvasFrame"),
  canvasContent: document.getElementById("canvasContent"),
  canvas: document.getElementById("imageCanvas"),
  emptyState: document.getElementById("emptyState"),
  prevPixel: document.getElementById("prevPixelButton"),
  nextPixel: document.getElementById("nextPixelButton"),
  zoomOut: document.getElementById("zoomOutButton"),
  zoomReset: document.getElementById("zoomResetButton"),
  zoomIn: document.getElementById("zoomInButton"),
  zoomLevel: document.getElementById("zoomLevel"),
  editPixels: document.getElementById("editPixelsButton"),
  resetAnnotations: document.getElementById("resetAnnotationsButton"),
  sampleForm: document.getElementById("sampleForm"),
  sampleCount: document.getElementById("sampleCountInput"),
  pixelPosition: document.getElementById("pixelPosition"),
  progressBar: document.getElementById("progressBar"),
  progressText: document.getElementById("progressText"),
  categoryButtons: document.getElementById("categoryButtons"),
  voteTotal: document.getElementById("voteTotal"),
  distributionList: document.getElementById("distributionList"),
  pixelList: document.getElementById("pixelList"),
  pixelCount: document.getElementById("pixelCount"),
  jsonExport: document.getElementById("jsonExport"),
  csvExport: document.getElementById("csvExport"),
  toast: document.getElementById("toast"),
};

const ctx = els.canvas.getContext("2d");

function userName() {
  const value = els.username.value.trim();
  return value || "guest";
}

function categoryById(id) {
  return state.categories.find((category) => category.id === id) || null;
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.classList.remove("visible");
  }, 2600);
}

function resetPixelCountControls() {
  els.pixelCountInput.value = DEFAULT_PIXEL_COUNT;
  els.batchPixelCount.value = DEFAULT_PIXEL_COUNT;
  els.sampleCount.value = DEFAULT_PIXEL_COUNT;
}

function setActiveUser(username) {
  const cleanUser = username.trim();
  els.username.value = cleanUser;
  localStorage.setItem("pixel-annotator-user", cleanUser);
}

function fillUserSelect(select, options = {}) {
  const emptyLabel = options.emptyLabel || "No saved users";
  const valueMode = options.valueMode || "username";
  select.innerHTML = "";
  if (!state.users.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = emptyLabel;
    select.appendChild(option);
    select.disabled = true;
    return;
  }

  select.disabled = false;
  const savedUser = localStorage.getItem("pixel-annotator-user") || "";
  for (const user of state.users) {
    const option = document.createElement("option");
    option.value = valueMode === "id" ? String(user.id) : user.username;
    option.textContent = user.username;
    option.selected = user.username === savedUser;
    select.appendChild(option);
  }
}

function selectedSettingsUser() {
  const userId = Number(els.userSettingsSelect.value || 0);
  return state.users.find((user) => user.id === userId) || null;
}

function renderUserSelect() {
  fillUserSelect(els.username);
  fillUserSelect(els.userSelect);
  fillUserSelect(els.userSettingsSelect, { valueMode: "id" });
  const activeUser = localStorage.getItem("pixel-annotator-user") || "";
  if (activeUser && state.users.some((user) => user.username === activeUser)) {
    els.username.value = activeUser;
    els.userSelect.value = activeUser;
  } else if (state.users.length) {
    setActiveUser(state.users[0].username);
    els.userSelect.value = state.users[0].username;
  }
  const settingsUser = selectedSettingsUser();
  els.userRename.value = settingsUser ? settingsUser.username : "";
}

async function loadUsers() {
  const data = await api("/api/users");
  state.users = data.users || [];
  renderUserSelect();
}

function openUserDialog() {
  renderUserSelect();
  const savedUser = localStorage.getItem("pixel-annotator-user") || "";
  const savedExists = state.users.some((user) => user.username === savedUser);
  els.userCreate.value = savedUser && !savedExists ? savedUser : "";
  if (typeof els.userDialog.showModal === "function") {
    els.userDialog.showModal();
  } else {
    els.userDialog.setAttribute("open", "");
  }
  if (els.userCreate.value || !state.users.length) {
    els.userCreate.focus();
  } else {
    els.userSelect.focus();
  }
}

function closeUserDialog() {
  if (typeof els.userDialog.close === "function") {
    els.userDialog.close();
  } else {
    els.userDialog.removeAttribute("open");
  }
}

async function chooseUser(event) {
  event.preventDefault();
  const newUser = els.userCreate.value.trim();
  const existingUser = els.userSelect.disabled ? "" : els.userSelect.value.trim();
  const username = newUser || existingUser;
  if (!username) {
    showToast("Choose or create a username.");
    return;
  }

  const user = await api("/api/users", {
    method: "POST",
    body: { username },
  });
  setActiveUser(user.username);
  await loadUsers();
  closeUserDialog();
  await bootstrap(false);
}

async function updateActiveUserFromInput() {
  const username = els.username.value.trim();
  if (!username) {
    openUserDialog();
    return;
  }
  setActiveUser(username);
  await bootstrap(true);
}

function openUserSettings() {
  renderUserSelect();
  if (typeof els.userSettingsDialog.showModal === "function") {
    els.userSettingsDialog.showModal();
  } else {
    els.userSettingsDialog.setAttribute("open", "");
  }
  if (state.users.length) {
    els.userSettingsSelect.focus();
  } else {
    els.userAdd.focus();
  }
}

function closeUserSettings() {
  if (typeof els.userSettingsDialog.close === "function") {
    els.userSettingsDialog.close();
  } else {
    els.userSettingsDialog.removeAttribute("open");
  }
}

async function addUser(event) {
  event.preventDefault();
  const username = els.userAdd.value.trim();
  if (!username) {
    return;
  }
  const user = await api("/api/users", {
    method: "POST",
    body: { username },
  });
  els.userAdd.value = "";
  setActiveUser(user.username);
  await loadUsers();
  els.userSettingsSelect.value = String(user.id);
  els.userRename.value = user.username;
  await bootstrap(true);
  showToast("User added.");
}

async function renameUser(event) {
  event.preventDefault();
  const user = selectedSettingsUser();
  const username = els.userRename.value.trim();
  if (!user || !username) {
    return;
  }
  const wasActive = user.username === userName();
  const updated = await api(`/api/users/${user.id}`, {
    method: "PUT",
    body: { username },
  });
  if (wasActive) {
    setActiveUser(updated.username);
  }
  await loadUsers();
  els.userSettingsSelect.value = String(updated.id);
  els.userRename.value = updated.username;
  await bootstrap(true);
  showToast("User renamed.");
}

async function deleteUser() {
  const user = selectedSettingsUser();
  if (!user) {
    return;
  }
  const ok = window.confirm(`Delete user "${user.username}" and their annotations?`);
  if (!ok) {
    return;
  }
  const wasActive = user.username === userName();
  const result = await api(`/api/users/${user.id}`, {
    method: "DELETE",
  });
  await loadUsers();
  if (!state.users.length) {
    localStorage.removeItem("pixel-annotator-user");
    els.username.value = "";
    closeUserSettings();
    clearCurrentImage();
    renderAll();
    openUserDialog();
  } else if (wasActive) {
    setActiveUser(state.users[0].username);
    await bootstrap(false);
  } else {
    await bootstrap(true);
  }
  showToast(`User deleted. ${result.deleted_annotations} annotations removed.`);
}

async function initializeApp() {
  const savedUser = localStorage.getItem("pixel-annotator-user") || "";
  els.username.value = savedUser;
  await loadUsers();
  openUserDialog();
}

async function api(path, options = {}) {
  const fetchOptions = { ...options };
  fetchOptions.headers = fetchOptions.headers || {};
  if (fetchOptions.body && !(fetchOptions.body instanceof FormData)) {
    fetchOptions.headers["Content-Type"] = "application/json";
    fetchOptions.body = JSON.stringify(fetchOptions.body);
  }

  const response = await fetch(path, fetchOptions);
  const contentType = response.headers.get("Content-Type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = payload && payload.error ? payload.error : `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

async function bootstrap(keepCurrent = true) {
  const currentId = state.detail?.image?.id;
  const datasetQuery = state.currentDatasetId ? `&dataset_id=${state.currentDatasetId}` : "";
  const data = await api(`/api/bootstrap?user=${encodeURIComponent(userName())}${datasetQuery}`);
  state.users = data.users || state.users;
  state.datasets = data.datasets;
  state.currentDatasetId = data.active_dataset_id;
  localStorage.setItem("pixel-annotator-dataset-id", state.currentDatasetId);
  state.categories = data.categories;
  state.images = data.images;
  renderUserSelect();
  renderDatasets();
  renderCategories();
  renderImages();

  if (keepCurrent && currentId && state.images.some((image) => image.id === currentId)) {
    await loadImage(currentId, false);
  } else if (!state.detail && state.images.length) {
    await loadImage(state.images[0].id, false);
  } else if (state.images.length) {
    clearCurrentImage();
    await loadImage(state.images[0].id, false);
  } else {
    clearCurrentImage();
    renderAll();
  }
}

async function loadImage(imageId, announce = true) {
  const detail = await api(`/api/images/${imageId}?user=${encodeURIComponent(userName())}`);
  state.detail = detail;
  state.categories = detail.categories;
  state.pixels = detail.pixels;
  state.currentIndex = clampCurrentIndex(state.currentIndex);
  state.zoom = 1;
  state.imageElement = await loadBrowserImage(detail.image.url);
  if (announce) {
    showToast(detail.image.name);
  }
  renderAll();
}

function clearCurrentImage() {
  state.detail = null;
  state.pixels = [];
  state.currentIndex = 0;
  state.imageElement = null;
  state.fitScale = 1;
  state.scale = 1;
  state.zoom = 1;
  state.pan.active = false;
  state.pan.moved = false;
  state.pan.pointerId = null;
  state.pan.suppressClick = false;
}

function loadBrowserImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Could not load image."));
    image.src = `${url}?t=${Date.now()}`;
  });
}

function renderAll() {
  renderDatasets();
  renderImages();
  renderCategories();
  renderExports();
  renderCanvas();
  renderInspector();
  renderPixels();
}

function renderDatasets() {
  els.datasetSelect.innerHTML = "";
  for (const dataset of state.datasets) {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.textContent = `${dataset.name} (${dataset.image_count})`;
    option.selected = dataset.id === state.currentDatasetId;
    els.datasetSelect.appendChild(option);
  }

  const active = state.datasets.find((dataset) => dataset.id === state.currentDatasetId);
  els.datasetImageCount.textContent = active ? active.image_count : 0;
  els.datasetRename.value = active ? active.name : "";
  els.datasetRename.disabled = !active;
}

function renderImages() {
  els.imageCount.textContent = state.images.length;
  els.imageList.innerHTML = "";

  if (!state.images.length) {
    els.imageList.innerHTML = `<div class="meta-line">No images</div>`;
    return;
  }

  for (const image of state.images) {
    const item = document.createElement("div");
    item.className = "image-item";
    item.tabIndex = 0;
    item.setAttribute("role", "button");
    item.setAttribute("aria-label", `Open ${image.name}`);
    if (state.detail?.image?.id === image.id) {
      item.classList.add("active");
    }
    item.innerHTML = `
      <img class="thumb" alt="" src="${image.url}">
      <span>
        <span class="image-title">${escapeHtml(image.name)}</span>
        <span class="image-meta">${image.width} x ${image.height} | ${image.annotated_count}/${image.pixel_count}</span>
      </span>
      <span class="pill">${image.pixel_count}</span>
    `;

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button square danger image-delete";
    deleteButton.textContent = "×";
    deleteButton.title = `Delete ${image.name}`;
    deleteButton.setAttribute("aria-label", `Delete ${image.name}`);
    deleteButton.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteImage(image).catch(reportError);
    });
    item.appendChild(deleteButton);

    const openImage = () => {
      state.currentIndex = 0;
      loadImage(image.id).catch(reportError);
    };
    item.addEventListener("click", openImage);
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openImage();
      }
    });
    els.imageList.appendChild(item);
  }
}

function renderCategories() {
  els.categoryLegend.innerHTML = "";
  for (const category of state.categories) {
    const item = document.createElement("div");
    item.className = "label-item";

    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = category.color;
    colorInput.title = `${category.name} color`;

    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = category.name;
    nameInput.spellcheck = false;
    nameInput.setAttribute("aria-label", `${category.name} label name`);

    const saveButton = document.createElement("button");
    saveButton.type = "button";
    saveButton.className = "button square";
    saveButton.textContent = "OK";
    saveButton.title = `Rename ${category.name}`;
    saveButton.addEventListener("click", () => {
      updateCategory(category.id, nameInput.value, colorInput.value).catch(reportError);
    });

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "button square danger";
    deleteButton.textContent = "x";
    deleteButton.title = `Remove ${category.name}`;
    deleteButton.addEventListener("click", () => {
      deleteCategory(category).catch(reportError);
    });

    item.append(colorInput, nameInput, saveButton, deleteButton);
    els.categoryLegend.appendChild(item);
  }
}

function renderExports() {
  const imageId = state.detail?.image?.id;
  if (!imageId) {
    els.jsonExport.href = "#";
    els.csvExport.href = "#";
    els.jsonExport.removeAttribute("download");
    els.csvExport.removeAttribute("download");
    els.jsonExport.classList.add("disabled");
    els.csvExport.classList.add("disabled");
    return;
  }
  els.jsonExport.href = `/api/images/${imageId}/export.json`;
  els.csvExport.href = `/api/images/${imageId}/export.csv`;
  els.jsonExport.download = `pixel-distribution-image-${imageId}.json`;
  els.csvExport.download = `pixel-distribution-image-${imageId}.csv`;
  els.jsonExport.classList.remove("disabled");
  els.csvExport.classList.remove("disabled");
}

function renderCanvas() {
  const image = state.imageElement;
  els.emptyState.style.display = image ? "none" : "block";
  els.zoomLevel.textContent = `${Math.round(state.zoom * 100)}%`;
  els.canvasFrame.classList.toggle("is-zoomed", state.zoom > 1.01);
  els.canvasFrame.classList.toggle("is-dragging", state.pan.active && state.pan.moved);
  els.canvasFrame.classList.toggle("is-editing-pixels", state.editPixelsMode);
  if (!image || !state.detail) {
    ctx.clearRect(0, 0, els.canvas.width, els.canvas.height);
    els.canvas.width = 1;
    els.canvas.height = 1;
    els.canvas.style.width = "1px";
    els.canvas.style.height = "1px";
    return;
  }

  const frame = els.canvasFrame.getBoundingClientRect();
  const padding = 72;
  const maxWidth = Math.max(120, frame.width - padding);
  const maxHeight = Math.max(120, frame.height - padding);
  state.fitScale = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight);
  state.scale = state.fitScale * state.zoom;
  state.displayWidth = Math.max(1, Math.round(image.naturalWidth * state.scale));
  state.displayHeight = Math.max(1, Math.round(image.naturalHeight * state.scale));

  const dpr = window.devicePixelRatio || 1;
  els.canvas.style.width = `${state.displayWidth}px`;
  els.canvas.style.height = `${state.displayHeight}px`;
  els.canvas.width = Math.round(state.displayWidth * dpr);
  els.canvas.height = Math.round(state.displayHeight * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, state.displayWidth, state.displayHeight);
  ctx.drawImage(image, 0, 0, state.displayWidth, state.displayHeight);
  drawPixelMarkers();
}

function drawPixelMarkers() {
  const pixels = state.pixels;
  const scale = state.scale;
  for (let index = 0; index < pixels.length; index += 1) {
    const pixel = pixels[index];
    const userCategory = categoryById(pixel.user_category_id);
    const consensus = pixel.consensus;
    const color = userCategory?.color || consensus?.color || "#ffffff";
    const x = (pixel.x + 0.5) * scale;
    const y = (pixel.y + 0.5) * scale;
    const active = index === state.currentIndex;
    const size = active ? 13 : 8;

    ctx.save();
    ctx.fillStyle = color;
    ctx.strokeStyle = active ? "#ffffff" : "rgba(0,0,0,0.74)";
    ctx.lineWidth = active ? 2 : 1.5;
    ctx.globalAlpha = userCategory || consensus ? 0.96 : 0.72;
    ctx.fillRect(Math.round(x - size / 2), Math.round(y - size / 2), size, size);
    ctx.strokeRect(Math.round(x - size / 2) + 0.5, Math.round(y - size / 2) + 0.5, size, size);
    if (active) {
      ctx.strokeStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(x, y, 11, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }
}

function renderInspector() {
  const total = state.pixels.length;
  const done = state.detail?.progress?.done || 0;
  const percent = total ? (done / total) * 100 : 0;
  els.progressBar.style.width = `${percent}%`;
  els.progressText.textContent = `${done} / ${total}`;
  els.pixelCount.textContent = total;

  const pixel = currentPixel();
  els.pixelPosition.textContent = pixel ? `${pixel.x}, ${pixel.y}` : "-";
  els.voteTotal.textContent = pixel ? `${pixel.total_votes} votes` : "0 votes";

  renderCategoryButtons(pixel);
  renderDistribution(pixel);
}

function renderCategoryButtons(pixel) {
  els.categoryButtons.innerHTML = "";
  for (const category of state.categories) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "button category-button";
    button.style.setProperty("--category-color", category.color);
    button.textContent = category.name;
    if (pixel?.user_category_id === category.id) {
      button.classList.add("selected");
    }
    button.disabled = !pixel;
    button.addEventListener("click", () => annotate(category.id));
    els.categoryButtons.appendChild(button);
  }
}

function renderDistribution(pixel) {
  els.distributionList.innerHTML = "";
  const distribution = pixel?.distribution || state.categories.map((category) => ({
    category_id: category.id,
    name: category.name,
    color: category.color,
    votes: 0,
    probability: 0,
  }));

  for (const item of distribution) {
    const row = document.createElement("div");
    row.className = "distribution-row";
    const percent = Math.round(item.probability * 100);
    row.innerHTML = `
      <span class="distribution-name">${escapeHtml(item.name)}</span>
      <span class="distribution-track">
        <span class="distribution-fill" style="--category-color: ${item.color}; width: ${item.probability * 100}%"></span>
      </span>
      <span class="image-meta">${percent}% / ${item.votes}</span>
    `;
    els.distributionList.appendChild(row);
  }
}

function renderPixels() {
  els.pixelList.innerHTML = "";
  if (!state.pixels.length) {
    els.pixelList.innerHTML = `<div class="meta-line">No target pixels</div>`;
    return;
  }

  state.pixels.slice(0, 300).forEach((pixel, index) => {
    const category = categoryById(pixel.user_category_id) || pixel.consensus;
    const item = document.createElement("button");
    item.type = "button";
    item.className = "pixel-item";
    if (index === state.currentIndex) {
      item.classList.add("active");
    }
    item.innerHTML = `
      <span>
        <span class="pixel-title">#${index + 1} (${pixel.x}, ${pixel.y})</span>
        <span class="pixel-meta">${pixel.total_votes} votes</span>
      </span>
      <span class="pixel-status" style="--category-color: ${category?.color || "#c5cdd4"}"></span>
    `;
    item.addEventListener("click", () => {
      state.currentIndex = index;
      renderAll();
    });
    els.pixelList.appendChild(item);
  });
}

function currentPixel() {
  return state.pixels[clampCurrentIndex(state.currentIndex)] || null;
}

function clampCurrentIndex(index) {
  if (!state.pixels.length) {
    return 0;
  }
  return Math.max(0, Math.min(index, state.pixels.length - 1));
}

async function annotate(categoryId) {
  const pixel = currentPixel();
  if (!pixel) {
    showToast("No target pixel selected.");
    return;
  }
  const selectedPixelId = pixel.id;
  await api("/api/annotations", {
    method: "POST",
    body: {
      pixel_id: selectedPixelId,
      username: userName(),
      category_id: categoryId,
    },
  });
  await refreshCurrentImage();
  const current = state.pixels.findIndex((item) => item.id === selectedPixelId);
  const nextUnlabeled = findNextUnlabeled(current + 1);
  state.currentIndex = nextUnlabeled >= 0 ? nextUnlabeled : clampCurrentIndex(current + 1);
  renderAll();
}

function findNextUnlabeled(startIndex) {
  for (let index = startIndex; index < state.pixels.length; index += 1) {
    if (!state.pixels[index].user_category_id) {
      return index;
    }
  }
  for (let index = 0; index < startIndex; index += 1) {
    if (!state.pixels[index].user_category_id) {
      return index;
    }
  }
  return -1;
}

async function refreshCurrentImage() {
  if (!state.detail?.image?.id) {
    return;
  }
  const currentId = state.detail.image.id;
  const detail = await api(`/api/images/${currentId}?user=${encodeURIComponent(userName())}`);
  state.detail = detail;
  state.categories = detail.categories;
  state.pixels = detail.pixels;
  state.currentIndex = clampCurrentIndex(state.currentIndex);
  const datasetQuery = state.currentDatasetId ? `&dataset_id=${state.currentDatasetId}` : "";
  const bootstrapData = await api(`/api/bootstrap?user=${encodeURIComponent(userName())}${datasetQuery}`);
  state.datasets = bootstrapData.datasets;
  state.currentDatasetId = bootstrapData.active_dataset_id;
  state.images = bootstrapData.images;
}

function previousPixel() {
  if (!state.pixels.length) {
    return;
  }
  state.currentIndex = (state.currentIndex - 1 + state.pixels.length) % state.pixels.length;
  renderAll();
}

function nextPixel() {
  if (!state.pixels.length) {
    return;
  }
  state.currentIndex = (state.currentIndex + 1) % state.pixels.length;
  renderAll();
}

function zoomAnchorFromClient(clientX, clientY) {
  const canvasRect = els.canvas.getBoundingClientRect();
  const frameRect = els.canvasFrame.getBoundingClientRect();
  const imageWidth = state.imageElement?.naturalWidth || 1;
  const imageHeight = state.imageElement?.naturalHeight || 1;
  return {
    imageX: Math.max(0, Math.min(imageWidth, (clientX - canvasRect.left) / state.scale)),
    imageY: Math.max(0, Math.min(imageHeight, (clientY - canvasRect.top) / state.scale)),
    frameX: clientX - frameRect.left,
    frameY: clientY - frameRect.top,
  };
}

function canvasScrollOrigin() {
  const canvasRect = els.canvas.getBoundingClientRect();
  const frameRect = els.canvasFrame.getBoundingClientRect();
  return {
    x: els.canvasFrame.scrollLeft + canvasRect.left - frameRect.left,
    y: els.canvasFrame.scrollTop + canvasRect.top - frameRect.top,
  };
}

function clampFrameScroll() {
  els.canvasFrame.scrollLeft = Math.max(
    0,
    Math.min(
      els.canvasFrame.scrollLeft,
      els.canvasFrame.scrollWidth - els.canvasFrame.clientWidth,
    ),
  );
  els.canvasFrame.scrollTop = Math.max(
    0,
    Math.min(
      els.canvasFrame.scrollTop,
      els.canvasFrame.scrollHeight - els.canvasFrame.clientHeight,
    ),
  );
}

function setZoom(zoom, anchor = null) {
  const hasImage = Boolean(state.imageElement);
  let zoomAnchor = anchor;
  if (hasImage && !zoomAnchor) {
    const frameRect = els.canvasFrame.getBoundingClientRect();
    zoomAnchor = zoomAnchorFromClient(
      frameRect.left + frameRect.width / 2,
      frameRect.top + frameRect.height / 2,
    );
  }
  state.zoom = Math.max(0.25, Math.min(8, zoom));
  renderCanvas();
  if (hasImage && zoomAnchor) {
    const origin = canvasScrollOrigin();
    els.canvasFrame.scrollLeft = origin.x + zoomAnchor.imageX * state.scale - zoomAnchor.frameX;
    els.canvasFrame.scrollTop = origin.y + zoomAnchor.imageY * state.scale - zoomAnchor.frameY;
    clampFrameScroll();
  }
}

function zoomIn() {
  setZoom(state.zoom * 1.25);
}

function zoomOut() {
  setZoom(state.zoom / 1.25);
}

function resetZoom() {
  setZoom(1);
}

function wheelZoom(event) {
  if (!state.imageElement) {
    return;
  }
  event.preventDefault();
  const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
  setZoom(state.zoom * factor, zoomAnchorFromClient(event.clientX, event.clientY));
}

function startPan(event) {
  if (!state.imageElement || event.button !== 0) {
    return;
  }
  state.pan.active = true;
  state.pan.moved = false;
  state.pan.pointerId = event.pointerId;
  state.pan.startX = event.clientX;
  state.pan.startY = event.clientY;
  state.pan.scrollLeft = els.canvasFrame.scrollLeft;
  state.pan.scrollTop = els.canvasFrame.scrollTop;
  els.canvasFrame.setPointerCapture(event.pointerId);
}

function movePan(event) {
  if (!state.pan.active || event.pointerId !== state.pan.pointerId) {
    return;
  }
  const dx = event.clientX - state.pan.startX;
  const dy = event.clientY - state.pan.startY;
  if (Math.abs(dx) + Math.abs(dy) > 4) {
    state.pan.moved = true;
    state.pan.suppressClick = true;
    els.canvasFrame.classList.add("is-dragging");
  }
  if (state.pan.moved) {
    els.canvasFrame.scrollLeft = state.pan.scrollLeft - dx;
    els.canvasFrame.scrollTop = state.pan.scrollTop - dy;
    event.preventDefault();
  }
}

function endPan(event) {
  if (!state.pan.active || event.pointerId !== state.pan.pointerId) {
    return;
  }
  if (els.canvasFrame.hasPointerCapture(event.pointerId)) {
    els.canvasFrame.releasePointerCapture(event.pointerId);
  }
  state.pan.active = false;
  state.pan.pointerId = null;
  els.canvasFrame.classList.remove("is-dragging");
}

function canvasPoint(event) {
  const rect = els.canvas.getBoundingClientRect();
  return {
    displayX: event.clientX - rect.left,
    displayY: event.clientY - rect.top,
    imageX: Math.floor((event.clientX - rect.left) / state.scale),
    imageY: Math.floor((event.clientY - rect.top) / state.scale),
  };
}

function nearestPixelIndex(displayX, displayY) {
  let bestIndex = -1;
  let bestDistance = 14 * 14;
  for (let index = 0; index < state.pixels.length; index += 1) {
    const pixel = state.pixels[index];
    const px = (pixel.x + 0.5) * state.scale;
    const py = (pixel.y + 0.5) * state.scale;
    const distance = (px - displayX) ** 2 + (py - displayY) ** 2;
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  }
  return bestIndex;
}

async function handleCanvasClick(event) {
  if (state.pan.suppressClick) {
    state.pan.suppressClick = false;
    return;
  }
  if (!state.detail?.image?.id || !state.imageElement) {
    return;
  }
  const point = canvasPoint(event);
  if (
    point.imageX < 0 ||
    point.imageY < 0 ||
    point.imageX >= state.detail.image.width ||
    point.imageY >= state.detail.image.height
  ) {
    return;
  }

  const nearest = nearestPixelIndex(point.displayX, point.displayY);
  if (state.editPixelsMode) {
    if (nearest >= 0) {
      state.currentIndex = nearest;
      renderAll();
      return;
    }
    await moveCurrentPixel(point.imageX, point.imageY);
    return;
  }

  if (nearest >= 0) {
    state.currentIndex = nearest;
    renderAll();
  }
}

async function uploadImageFile(file, name, pixelCount) {
  const data = new FormData();
  data.append("image", file);
  data.append("name", name);
  data.append("pixel_count", pixelCount);
  data.append("user", userName());
  data.append("dataset_id", state.currentDatasetId || "");
  return api("/api/images", { method: "POST", body: data });
}

async function uploadImage(event) {
  event.preventDefault();
  const file = els.imageInput.files[0];
  if (!file) {
    showToast("Choose an image first.");
    return;
  }
  const detail = await uploadImageFile(file, els.imageName.value, els.pixelCountInput.value);
  state.detail = detail;
  state.pixels = detail.pixels;
  state.categories = detail.categories;
  state.currentIndex = 0;
  state.imageElement = await loadBrowserImage(detail.image.url);
  els.uploadForm.reset();
  els.pixelCountInput.value = DEFAULT_PIXEL_COUNT;
  await bootstrap(true);
  showToast(`${detail.inserted_pixels} target pixels created.`);
}

async function batchUploadImages(event) {
  event.preventDefault();
  const files = Array.from(els.batchImageInput.files || []);
  if (!files.length) {
    showToast("Choose images first.");
    return;
  }

  let lastDetail = null;
  for (const file of files) {
    lastDetail = await uploadImageFile(file, file.name, els.batchPixelCount.value);
  }

  closeBatchDialog();
  els.batchForm.reset();
  els.batchPixelCount.value = DEFAULT_PIXEL_COUNT;
  if (lastDetail) {
    state.currentIndex = 0;
    await bootstrap(false);
    await loadImage(lastDetail.image.id, false);
  }
  showToast(`${files.length} images uploaded.`);
}

async function moveCurrentPixel(x, y) {
  const pixel = currentPixel();
  if (!pixel) {
    showToast("No target pixel selected.");
    return;
  }
  const moved = await api(`/api/pixels/${pixel.id}`, {
    method: "PUT",
    body: { x, y },
  });
  await refreshCurrentImage();
  state.currentIndex = Math.max(0, state.pixels.findIndex((item) => item.id === moved.id));
  renderAll();
  showToast(`Pixel moved. ${moved.deleted_annotations} annotations cleared.`);
}

async function resetImageAnnotations() {
  if (!state.detail?.image?.id) {
    showToast("No image selected.");
    return;
  }
  const ok = window.confirm(`Reset all target pixels and annotations for "${state.detail.image.name}"?`);
  if (!ok) {
    return;
  }
  const result = await api(`/api/images/${state.detail.image.id}/pixels`, {
    method: "DELETE",
  });
  await refreshCurrentImage();
  resetPixelCountControls();
  renderAll();
  showToast(`${result.deleted_pixels} target pixels removed.`);
}

function toggleEditPixels() {
  state.editPixelsMode = !state.editPixelsMode;
  els.editPixels.classList.toggle("active", state.editPixelsMode);
  renderCanvas();
}

function openBatchDialog() {
  els.batchForm.reset();
  els.batchPixelCount.value = els.pixelCountInput.value || DEFAULT_PIXEL_COUNT;
  if (typeof els.batchDialog.showModal === "function") {
    els.batchDialog.showModal();
    return;
  }
  els.batchDialog.setAttribute("open", "");
}

function closeBatchDialog() {
  if (typeof els.batchDialog.close === "function") {
    els.batchDialog.close();
    return;
  }
  els.batchDialog.removeAttribute("open");
}

async function addCategory(event) {
  event.preventDefault();
  const name = els.categoryName.value.trim();
  if (!name) {
    return;
  }
  await api("/api/categories", {
    method: "POST",
    body: {
      name,
      color: els.categoryColor.value,
    },
  });
  els.categoryName.value = "";
  await bootstrap(true);
}

async function createDataset(event) {
  event.preventDefault();
  const name = els.datasetName.value.trim();
  if (!name) {
    return;
  }
  const dataset = await api("/api/datasets", {
    method: "POST",
    body: { name },
  });
  state.currentDatasetId = dataset.id;
  localStorage.setItem("pixel-annotator-dataset-id", dataset.id);
  els.datasetName.value = "";
  clearCurrentImage();
  await bootstrap(false);
  showToast("Dataset saved.");
}

async function renameDataset(event) {
  event.preventDefault();
  const name = els.datasetRename.value.trim();
  if (!state.currentDatasetId || !name) {
    return;
  }
  await api(`/api/datasets/${state.currentDatasetId}`, {
    method: "PUT",
    body: { name },
  });
  await bootstrap(true);
  showToast("Dataset renamed.");
}

async function changeDataset() {
  state.currentDatasetId = Number(els.datasetSelect.value) || null;
  localStorage.setItem("pixel-annotator-dataset-id", state.currentDatasetId || "");
  clearCurrentImage();
  await bootstrap(false);
}

async function updateCategory(categoryId, name, color) {
  await api(`/api/categories/${categoryId}`, {
    method: "PUT",
    body: { name, color },
  });
  await bootstrap(true);
  showToast("Label saved.");
}

async function deleteCategory(category) {
  const ok = window.confirm(`Remove label "${category.name}" and its annotations?`);
  if (!ok) {
    return;
  }
  const result = await api(`/api/categories/${category.id}`, {
    method: "DELETE",
  });
  await bootstrap(true);
  showToast(`Label removed. ${result.deleted_annotations} annotations cleared.`);
}

async function deleteImage(image) {
  const ok = window.confirm(`Delete image "${image.name}" and all of its annotations?`);
  if (!ok) {
    return;
  }
  const wasCurrent = state.detail?.image?.id === image.id;
  const result = await api(`/api/images/${image.id}`, {
    method: "DELETE",
  });
  if (wasCurrent) {
    clearCurrentImage();
  }
  await bootstrap(!wasCurrent);
  showToast(`Image deleted. ${result.deleted_annotations} annotations removed.`);
}

async function downloadExport(event, format) {
  event.preventDefault();
  const imageId = state.detail?.image?.id;
  if (!imageId) {
    showToast("No image selected.");
    return;
  }

  const response = await fetch(`/api/images/${imageId}/export.${format}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Download failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.error || message;
    } catch {
      // The response is not JSON; keep the status-based message.
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `pixel-distribution-image-${imageId}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function samplePixels(event) {
  event.preventDefault();
  if (!state.detail?.image?.id) {
    return;
  }
  const result = await api(`/api/images/${state.detail.image.id}/pixels/random`, {
    method: "POST",
    body: { count: Number(els.sampleCount.value || 0) },
  });
  await refreshCurrentImage();
  renderAll();
  showToast(`${result.inserted} target pixels added.`);
}

function reportError(error) {
  console.error(error);
  showToast(error.message || "Something went wrong.");
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

els.username.addEventListener("change", () => {
  updateActiveUserFromInput().catch(reportError);
});
els.username.addEventListener("blur", () => {
  if (els.username.value.trim()) {
    localStorage.setItem("pixel-annotator-user", els.username.value.trim());
  }
});
els.userSettings.addEventListener("click", openUserSettings);
els.userForm.addEventListener("submit", (event) => chooseUser(event).catch(reportError));
els.userDialog.addEventListener("cancel", (event) => {
  event.preventDefault();
});
els.userSettingsClose.addEventListener("click", closeUserSettings);
els.userSettingsSelect.addEventListener("change", () => {
  const user = selectedSettingsUser();
  els.userRename.value = user ? user.username : "";
});
els.userAddForm.addEventListener("submit", (event) => addUser(event).catch(reportError));
els.userRenameForm.addEventListener("submit", (event) => renameUser(event).catch(reportError));
els.userDelete.addEventListener("click", () => deleteUser().catch(reportError));
els.uploadForm.addEventListener("submit", (event) => uploadImage(event).catch(reportError));
els.batchUpload.addEventListener("click", openBatchDialog);
els.batchClose.addEventListener("click", closeBatchDialog);
els.batchForm.addEventListener("submit", (event) => batchUploadImages(event).catch(reportError));
els.datasetForm.addEventListener("submit", (event) => createDataset(event).catch(reportError));
els.datasetRenameForm.addEventListener("submit", (event) => renameDataset(event).catch(reportError));
els.datasetSelect.addEventListener("change", () => changeDataset().catch(reportError));
els.categoryForm.addEventListener("submit", (event) => addCategory(event).catch(reportError));
els.sampleForm.addEventListener("submit", (event) => samplePixels(event).catch(reportError));
els.jsonExport.addEventListener("click", (event) => downloadExport(event, "json").catch(reportError));
els.csvExport.addEventListener("click", (event) => downloadExport(event, "csv").catch(reportError));
els.prevPixel.addEventListener("click", previousPixel);
els.nextPixel.addEventListener("click", nextPixel);
els.zoomOut.addEventListener("click", zoomOut);
els.zoomReset.addEventListener("click", resetZoom);
els.zoomIn.addEventListener("click", zoomIn);
els.editPixels.addEventListener("click", toggleEditPixels);
els.resetAnnotations.addEventListener("click", () => resetImageAnnotations().catch(reportError));
els.canvasFrame.addEventListener("pointerdown", startPan);
els.canvasFrame.addEventListener("pointermove", movePan);
els.canvasFrame.addEventListener("pointerup", endPan);
els.canvasFrame.addEventListener("pointercancel", endPan);
els.canvasFrame.addEventListener("wheel", wheelZoom, { passive: false });
els.canvasFrame.addEventListener("click", (event) => handleCanvasClick(event).catch(reportError));
window.addEventListener("resize", () => renderCanvas());

initializeApp().catch(reportError);
