const LABELS = [
  "O",
  "B-HEADER",
  "I-HEADER",
  "B-QUESTION",
  "I-QUESTION",
  "B-ANSWER",
  "I-ANSWER",
];

const state = {
  images: [],
  currentIndex: -1,
  currentDoc: null,
  selectedToken: -1,
  selectedTokens: [],
  rotation: 0,
  zoom: 1,
  selectBoxMode: false,
  selectBoxStart: null,
  selectBoxAppend: false,
  addBoxMode: false,
  draftBoxStart: null,
};

const imageList = document.getElementById("image-list");
const imageStage = document.getElementById("image-stage");
const transformLayer = document.getElementById("transform-layer");
const pageImage = document.getElementById("page-image");
const boxLayer = document.getElementById("box-layer");
const drawLayer = document.getElementById("draw-layer");
const draftBox = document.getElementById("draft-box");
const selectionBox = document.getElementById("selection-box");
const viewer = document.getElementById("viewer");
const tokenText = document.getElementById("token-text");
const tokenLabel = document.getElementById("token-label");
const tokenBBox = document.getElementById("token-bbox");
const statusText = document.getElementById("status-text");
const zoomText = document.getElementById("zoom-text");
const showOLabels = document.getElementById("show-o-labels");
const selectBoxButton = document.getElementById("toggle-select-box");
const addBoxButton = document.getElementById("toggle-add-box");

function setStatus(text) {
  statusText.textContent = text;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new Error(payload.error || response.statusText);
  }
  return response.json();
}

function renderImageList() {
  imageList.innerHTML = "";
  state.images.forEach((item, index) => {
    const button = document.createElement("button");
    button.className = `image-item ${index === state.currentIndex ? "active" : ""} ${item.label_exists ? "done" : ""}`;
    button.textContent = item.name;
    button.addEventListener("click", () => loadImage(index, false));
    imageList.appendChild(button);
  });
}

function labelClass(label) {
  if (!label) {
    return "label-UNLABELED";
  }
  return `label-${label.replace(/[^A-Z-]/g, "")}`;
}

function getDisplayImageSize() {
  const naturalWidth = pageImage.naturalWidth || 0;
  const naturalHeight = pageImage.naturalHeight || 0;
  if (!naturalWidth || !naturalHeight) {
    return { width: 0, height: 0 };
  }

  const rotatedWidth = state.rotation === 90 || state.rotation === 270 ? naturalHeight : naturalWidth;
  const rotatedHeight = state.rotation === 90 || state.rotation === 270 ? naturalWidth : naturalHeight;
  const fitScale = Math.min(
    1,
    viewer.clientWidth / Math.max(rotatedWidth, 1),
    viewer.clientHeight / Math.max(rotatedHeight, 1),
  );
  const scale = Math.max(0.1, fitScale * state.zoom);

  return {
    width: naturalWidth * scale,
    height: naturalHeight * scale,
  };
}

function updateStageTransform() {
  const { width, height } = getDisplayImageSize();
  if (!width || !height) return;

  let stageWidth = width;
  let stageHeight = height;
  let transform = "translate(0px, 0px) rotate(0deg)";

  if (state.rotation === 90) {
    stageWidth = height;
    stageHeight = width;
    transform = `translate(${height}px, 0px) rotate(90deg)`;
  } else if (state.rotation === 180) {
    transform = `translate(${width}px, ${height}px) rotate(180deg)`;
  } else if (state.rotation === 270) {
    stageWidth = height;
    stageHeight = width;
    transform = `translate(0px, ${width}px) rotate(270deg)`;
  }

  pageImage.style.width = `${width}px`;
  pageImage.style.height = `${height}px`;
  imageStage.style.width = `${stageWidth}px`;
  imageStage.style.height = `${stageHeight}px`;
  transformLayer.style.width = `${width}px`;
  transformLayer.style.height = `${height}px`;
  transformLayer.style.transform = transform;
}

function updateAddBoxUI() {
  imageStage.classList.toggle("add-box-mode", state.addBoxMode);
  addBoxButton.classList.toggle("active-tool", state.addBoxMode);
  addBoxButton.textContent = state.addBoxMode ? "Cancel Add Box" : "Add Box";
}

function updateSelectBoxUI() {
  imageStage.classList.toggle("select-box-mode", state.selectBoxMode);
  selectBoxButton.classList.toggle("active-tool", state.selectBoxMode);
  selectBoxButton.textContent = state.selectBoxMode ? "Cancel Box Select" : "Box Select";
}

function hideDraftBox() {
  draftBox.classList.add("hidden");
}

function hideSelectionBox() {
  selectionBox.classList.add("hidden");
}

function updateZoomUI() {
  zoomText.textContent = `${Math.round(state.zoom * 100)}%`;
}

function renderBoxes() {
  boxLayer.innerHTML = "";
  if (!state.currentDoc) return;

  const { width, height } = getDisplayImageSize();
  if (!width || !height) return;
  updateStageTransform();

  state.currentDoc.tokens.forEach((token, index) => {
    if (!showOLabels.checked && token.label === "O") {
      return;
    }
    const [x1, y1, x2, y2] = token.bbox;
    const box = document.createElement("div");
    box.className = `token-box ${labelClass(token.label)} ${state.selectedTokens.includes(index) ? "selected" : ""}`;
    box.style.left = `${(x1 / 1000) * width}px`;
    box.style.top = `${(y1 / 1000) * height}px`;
    box.style.width = `${((x2 - x1) / 1000) * width}px`;
    box.style.height = `${((y2 - y1) / 1000) * height}px`;
    box.title = `${token.text} | ${token.label || "(unlabeled)"}`;
    box.addEventListener("click", (event) => selectToken(index, event));
    boxLayer.appendChild(box);
  });

  updateStageTransform();
}

function getOrderedSelection() {
  return [...state.selectedTokens].sort((left, right) => left - right);
}

function selectToken(index, event = null) {
  const toggleSelection = Boolean(event && (event.ctrlKey || event.metaKey));
  if (toggleSelection) {
    if (state.selectedTokens.includes(index)) {
      state.selectedTokens = state.selectedTokens.filter((value) => value !== index);
    } else {
      state.selectedTokens = [...state.selectedTokens, index];
    }
  } else {
    state.selectedTokens = [index];
  }
  if (!state.selectedTokens.length) {
    clearSelection();
    return;
  }
  state.selectedToken = state.selectedTokens.includes(index) ? index : getOrderedSelection()[0];
  const token = state.currentDoc.tokens[state.selectedToken];
  tokenText.value = token.text;
  tokenLabel.value = token.label || "";
  tokenBBox.value = token.bbox.join(", ");
  renderBoxes();
}

function syncSelectedToken() {
  if (state.selectedToken < 0 || !state.currentDoc) return;
  const token = state.currentDoc.tokens[state.selectedToken];
  token.text = tokenText.value;
  token.label = tokenLabel.value;
  const selectedSet = new Set(state.selectedTokens);
  state.currentDoc.tokens.forEach((candidate, index) => {
    if (index !== state.selectedToken && selectedSet.has(index)) {
      candidate.label = token.label;
    }
  });
  renderBoxes();
}

function clearSelection() {
  state.selectedToken = -1;
  state.selectedTokens = [];
  tokenText.value = "";
  tokenLabel.value = "";
  tokenBBox.value = "";
  renderBoxes();
}

function bboxEquals(left, right) {
  return Array.isArray(left)
    && Array.isArray(right)
    && left.length === right.length
    && left.every((value, index) => value === right[index]);
}

function makeSeedRef(text, bbox) {
  return `${text}::${bbox.join(",")}`;
}

function getTokenSeedRefs(token) {
  if (Array.isArray(token.seed_refs) && token.seed_refs.length) {
    return token.seed_refs;
  }
  if (token.seed_text && Array.isArray(token.seed_bbox)) {
    return [makeSeedRef(token.seed_text, token.seed_bbox)];
  }
  if (token.source === "ocr" && token.text && Array.isArray(token.bbox)) {
    return [makeSeedRef(token.text, token.bbox)];
  }
  return [];
}

function isTokenModified(token) {
  if (token.source === "manual" || token.source === "merged") {
    return true;
  }
  if ((token.label || "") !== "") {
    return true;
  }
  if (token.seed_text !== undefined && token.text !== token.seed_text) {
    return true;
  }
  if (Array.isArray(token.seed_bbox) && !bboxEquals(token.bbox, token.seed_bbox)) {
    return true;
  }
  return false;
}

function mergeReloadedOCR(existingDoc, freshDoc) {
  const ignoredRefs = new Set(existingDoc.ignored_ocr_refs || []);
  const preservedTokens = existingDoc.tokens.filter((token) => isTokenModified(token));
  preservedTokens.forEach((token) => {
    getTokenSeedRefs(token).forEach((ref) => ignoredRefs.add(ref));
  });
  const freshTokens = freshDoc.tokens.filter((token) => {
    const refs = getTokenSeedRefs(token);
    return !refs.some((ref) => ignoredRefs.has(ref));
  });
  return {
    ...freshDoc,
    rotation: existingDoc.rotation,
    ignored_ocr_refs: Array.from(ignoredRefs),
    tokens: [...preservedTokens, ...freshTokens],
  };
}

function toggleAddBoxMode(forceValue = null) {
  state.addBoxMode = forceValue ?? !state.addBoxMode;
  if (state.addBoxMode) {
    state.selectBoxMode = false;
    state.selectBoxStart = null;
    state.selectBoxAppend = false;
    hideSelectionBox();
    updateSelectBoxUI();
  }
  state.draftBoxStart = null;
  hideDraftBox();
  updateAddBoxUI();
  if (state.addBoxMode) {
    setStatus("Add-box mode enabled: click the first corner of the new token box");
  }
}

function toggleSelectBoxMode(forceValue = null) {
  state.selectBoxMode = forceValue ?? !state.selectBoxMode;
  if (state.selectBoxMode) {
    state.addBoxMode = false;
    state.draftBoxStart = null;
    hideDraftBox();
    updateAddBoxUI();
  }
  state.selectBoxStart = null;
  state.selectBoxAppend = false;
  hideSelectionBox();
  updateSelectBoxUI();
  if (state.selectBoxMode) {
    setStatus("Box-select mode enabled: drag a rectangle to select multiple tokens");
  }
}

function setZoom(nextZoom) {
  state.zoom = clamp(nextZoom, 0.25, 6);
  updateZoomUI();
  renderBoxes();
}

function adjustZoom(delta) {
  const nextZoom = Math.round((state.zoom + delta) * 100) / 100;
  setZoom(nextZoom);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeBBox(bbox) {
  let [x1, y1, x2, y2] = bbox;
  x1 = clamp(x1, 0, 999);
  y1 = clamp(y1, 0, 999);
  x2 = clamp(x2, 1, 1000);
  y2 = clamp(y2, 1, 1000);
  if (x2 <= x1) {
    x2 = clamp(x1 + 1, 1, 1000);
    x1 = clamp(x2 - 1, 0, 999);
  }
  if (y2 <= y1) {
    y2 = clamp(y1 + 1, 1, 1000);
    y1 = clamp(y2 - 1, 0, 999);
  }
  return [x1, y1, x2, y2];
}

function getViewPointFromClient(clientX, clientY) {
  const rect = imageStage.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }
  return {
    x: clamp((clientX - rect.left) / rect.width, 0, 1),
    y: clamp((clientY - rect.top) / rect.height, 0, 1),
  };
}

function viewPointToDocument(point) {
  switch (state.rotation) {
    case 90:
      return { x: point.y, y: 1 - point.x };
    case 180:
      return { x: 1 - point.x, y: 1 - point.y };
    case 270:
      return { x: 1 - point.y, y: point.x };
    default:
      return point;
  }
}

function documentPointToView(point) {
  switch (state.rotation) {
    case 90:
      return { x: 1 - point.y, y: point.x };
    case 180:
      return { x: 1 - point.x, y: 1 - point.y };
    case 270:
      return { x: point.y, y: 1 - point.x };
    default:
      return point;
  }
}

function renderDraftBox(start, end) {
  const rect = imageStage.getBoundingClientRect();
  const left = Math.min(start.x, end.x) * rect.width;
  const top = Math.min(start.y, end.y) * rect.height;
  const width = Math.abs(end.x - start.x) * rect.width;
  const height = Math.abs(end.y - start.y) * rect.height;
  draftBox.style.left = `${left}px`;
  draftBox.style.top = `${top}px`;
  draftBox.style.width = `${width}px`;
  draftBox.style.height = `${height}px`;
  draftBox.classList.remove("hidden");
}

function renderSelectionBox(start, end) {
  const rect = imageStage.getBoundingClientRect();
  const left = Math.min(start.x, end.x) * rect.width;
  const top = Math.min(start.y, end.y) * rect.height;
  const width = Math.abs(end.x - start.x) * rect.width;
  const height = Math.abs(end.y - start.y) * rect.height;
  selectionBox.style.left = `${left}px`;
  selectionBox.style.top = `${top}px`;
  selectionBox.style.width = `${width}px`;
  selectionBox.style.height = `${height}px`;
  selectionBox.classList.remove("hidden");
}

function createTokenFromDraft(start, end) {
  if (!state.currentDoc) {
    return null;
  }
  const startDoc = viewPointToDocument(start);
  const endDoc = viewPointToDocument(end);
  const bbox = normalizeBBox([
    Math.round(Math.min(startDoc.x, endDoc.x) * 1000),
    Math.round(Math.min(startDoc.y, endDoc.y) * 1000),
    Math.round(Math.max(startDoc.x, endDoc.x) * 1000),
    Math.round(Math.max(startDoc.y, endDoc.y) * 1000),
  ]);
  const newToken = {
    text: "",
    bbox,
    label: tokenLabel.value || "",
    source: "manual",
    seed_refs: [],
  };
  state.currentDoc.tokens.push(newToken);
  const index = state.currentDoc.tokens.length - 1;
  selectToken(index);
  tokenText.focus();
  setStatus("Added new token box");
  return index;
}

async function runOCRForToken(index) {
  if (!state.currentDoc || state.currentIndex < 0) {
    return;
  }
  const image = state.images[state.currentIndex];
  const token = state.currentDoc.tokens[index];
  if (!image || !token) {
    return;
  }
  try {
    setStatus("Running OCR for new box...");
    const payload = await fetchJson(`/api/ocr-box/${encodeURIComponent(image.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bbox: token.bbox,
        rotation: state.rotation,
      }),
    });
    if (!state.currentDoc.tokens[index]) {
      return;
    }
    state.currentDoc.tokens[index].text = payload.text || "";
    if (state.selectedToken === index) {
      tokenText.value = state.currentDoc.tokens[index].text;
    }
    renderBoxes();
    setStatus(payload.text ? "OCR filled new token text" : "OCR found no text in new box");
  } catch (error) {
    setStatus(error.message);
  }
}

function tokenViewRect(token) {
  const [x1, y1, x2, y2] = token.bbox;
  const corners = [
    documentPointToView({ x: x1 / 1000, y: y1 / 1000 }),
    documentPointToView({ x: x2 / 1000, y: y1 / 1000 }),
    documentPointToView({ x: x1 / 1000, y: y2 / 1000 }),
    documentPointToView({ x: x2 / 1000, y: y2 / 1000 }),
  ];
  return {
    left: Math.min(...corners.map((point) => point.x)),
    top: Math.min(...corners.map((point) => point.y)),
    right: Math.max(...corners.map((point) => point.x)),
    bottom: Math.max(...corners.map((point) => point.y)),
  };
}

function rectsIntersect(left, right) {
  return !(
    left.right < right.left
    || left.left > right.right
    || left.bottom < right.top
    || left.top > right.bottom
  );
}

function applyBoxSelection(start, end, appendSelection) {
  if (!state.currentDoc) {
    return;
  }
  const selectionRect = {
    left: Math.min(start.x, end.x),
    top: Math.min(start.y, end.y),
    right: Math.max(start.x, end.x),
    bottom: Math.max(start.y, end.y),
  };
  const selected = state.currentDoc.tokens
    .map((token, index) => (rectsIntersect(tokenViewRect(token), selectionRect) ? index : null))
    .filter((index) => index !== null);
  const nextSelection = appendSelection
    ? Array.from(new Set([...state.selectedTokens, ...selected]))
    : selected;
  state.selectedTokens = nextSelection;
  state.selectedToken = nextSelection.length ? nextSelection[0] : -1;
  if (state.selectedToken >= 0) {
    const token = state.currentDoc.tokens[state.selectedToken];
    tokenText.value = token.text;
    tokenLabel.value = token.label || "";
    tokenBBox.value = token.bbox.join(", ");
  } else {
    tokenText.value = "";
    tokenLabel.value = "";
    tokenBBox.value = "";
  }
  renderBoxes();
  setStatus(`Selected ${nextSelection.length} token${nextSelection.length === 1 ? "" : "s"}`);
}

function updateBBoxField() {
  if (state.selectedToken < 0 || !state.currentDoc) {
    tokenBBox.value = "";
    return;
  }
  tokenBBox.value = state.currentDoc.tokens[state.selectedToken].bbox.join(", ");
}

function updateSelectedBBoxes(transform) {
  if (!state.currentDoc || !state.selectedTokens.length) {
    return false;
  }
  state.selectedTokens.forEach((index) => {
    const token = state.currentDoc.tokens[index];
    token.bbox = normalizeBBox(transform(token.bbox));
  });
  updateBBoxField();
  renderBoxes();
  return true;
}

function moveSelectedBBoxes(dx, dy) {
  return updateSelectedBBoxes(([x1, y1, x2, y2]) => {
    const width = x2 - x1;
    const height = y2 - y1;
    const nextX1 = clamp(x1 + dx, 0, 1000 - width);
    const nextY1 = clamp(y1 + dy, 0, 1000 - height);
    return [nextX1, nextY1, nextX1 + width, nextY1 + height];
  });
}

function resizeSelectedBBoxes(edge, delta) {
  return updateSelectedBBoxes(([x1, y1, x2, y2]) => {
    if (edge === "left") {
      x1 = clamp(x1 + delta, 0, x2 - 1);
    } else if (edge === "right") {
      x2 = clamp(x2 + delta, x1 + 1, 1000);
    } else if (edge === "top") {
      y1 = clamp(y1 + delta, 0, y2 - 1);
    } else if (edge === "bottom") {
      y2 = clamp(y2 + delta, y1 + 1, 1000);
    }
    return [x1, y1, x2, y2];
  });
}

function mapViewDeltaToDocument(dx, dy) {
  switch (state.rotation) {
    case 90:
      return [dy, -dx];
    case 180:
      return [-dx, -dy];
    case 270:
      return [-dy, dx];
    default:
      return [dx, dy];
  }
}

function mapViewResizeToDocument(key, step) {
  const mappings = {
    0: {
      ArrowLeft: ["left", -step],
      ArrowRight: ["right", step],
      ArrowUp: ["top", -step],
      ArrowDown: ["bottom", step],
    },
    90: {
      ArrowLeft: ["bottom", step],
      ArrowRight: ["top", -step],
      ArrowUp: ["left", -step],
      ArrowDown: ["right", step],
    },
    180: {
      ArrowLeft: ["right", step],
      ArrowRight: ["left", -step],
      ArrowUp: ["bottom", step],
      ArrowDown: ["top", -step],
    },
    270: {
      ArrowLeft: ["top", -step],
      ArrowRight: ["bottom", step],
      ArrowUp: ["right", step],
      ArrowDown: ["left", -step],
    },
  };
  return mappings[state.rotation][key];
}

function deleteSelectedToken() {
  if (!state.selectedTokens.length || !state.currentDoc) return;
  const toDelete = new Set(state.selectedTokens);
  const ignoredRefs = new Set(state.currentDoc.ignored_ocr_refs || []);
  state.currentDoc.tokens.forEach((token, index) => {
    if (toDelete.has(index)) {
      getTokenSeedRefs(token).forEach((ref) => ignoredRefs.add(ref));
    }
  });
  state.currentDoc.ignored_ocr_refs = Array.from(ignoredRefs);
  state.currentDoc.tokens = state.currentDoc.tokens.filter((_, index) => !toDelete.has(index));
  clearSelection();
  setStatus(`Deleted ${toDelete.size} token${toDelete.size === 1 ? "" : "s"}`);
}

function sortTokensForMerge(tokens) {
  return [...tokens].sort((left, right) => {
    const yDiff = left.bbox[1] - right.bbox[1];
    if (Math.abs(yDiff) > 12) {
      return yDiff;
    }
    return left.bbox[0] - right.bbox[0];
  });
}

function mergeSelectedTokens() {
  if (state.selectedTokens.length < 2 || !state.currentDoc) {
    return;
  }
  const orderedIndexes = getOrderedSelection();
  const selected = sortTokensForMerge(orderedIndexes.map((index) => state.currentDoc.tokens[index]));
  const labels = new Set(selected.map((token) => token.label));
  const mergedToken = {
    text: selected.map((token) => token.text).join(" "),
    bbox: [
      Math.min(...selected.map((token) => token.bbox[0])),
      Math.min(...selected.map((token) => token.bbox[1])),
      Math.max(...selected.map((token) => token.bbox[2])),
      Math.max(...selected.map((token) => token.bbox[3])),
    ],
    label: labels.size === 1 ? selected[0].label : tokenLabel.value,
    source: "merged",
    seed_refs: selected.flatMap((token) => getTokenSeedRefs(token)),
  };
  const mergeIndexes = new Set(orderedIndexes);
  const insertAt = orderedIndexes[0];
  const nextTokens = [];
  state.currentDoc.tokens.forEach((token, index) => {
    if (index === insertAt) {
      nextTokens.push(mergedToken);
    }
    if (!mergeIndexes.has(index)) {
      nextTokens.push(token);
    }
  });
  state.currentDoc.tokens = nextTokens;
  state.selectedTokens = [insertAt];
  state.selectedToken = insertAt;
  tokenText.value = mergedToken.text;
  tokenLabel.value = mergedToken.label || "";
  tokenBBox.value = mergedToken.bbox.join(", ");
  renderBoxes();
  setStatus(`Merged ${orderedIndexes.length} tokens`);
}

async function loadImages() {
  state.images = await fetchJson("/api/images");
  renderImageList();
  if (state.images.length && state.currentIndex === -1) {
    await loadImage(0, false);
  }
}

async function loadImage(index, forceReload) {
  state.currentIndex = index;
  const image = state.images[index];
  renderImageList();
  pageImage.onload = () => renderBoxes();
  pageImage.src = `/api/image/${encodeURIComponent(image.name)}?ts=${Date.now()}`;
  const suffix = forceReload ? `?reload=1&rotation=${state.rotation}` : "";
  const nextDoc = await fetchJson(`/api/label/${encodeURIComponent(image.name)}${suffix}`);
  state.currentDoc = forceReload && state.currentDoc
    ? mergeReloadedOCR(state.currentDoc, nextDoc)
    : nextDoc;
  const hasSavedRotation = Object.prototype.hasOwnProperty.call(state.currentDoc, "rotation");
  if (hasSavedRotation) {
    state.rotation = Number(state.currentDoc.rotation || 0) % 360;
  } else if (!forceReload) {
    state.rotation = 0;
  }
  if (!forceReload) {
    state.zoom = 1;
    updateZoomUI();
  }
  clearSelection();
  setStatus(forceReload ? `Reloaded OCR for ${image.name} at ${state.rotation}°` : `Loaded ${image.name}`);
}

async function saveCurrent() {
  if (!state.currentDoc || state.currentIndex < 0) return;
  syncSelectedToken();
  state.currentDoc.rotation = state.rotation;
  state.currentDoc.ignored_ocr_refs = state.currentDoc.ignored_ocr_refs || [];
  const image = state.images[state.currentIndex];
  await fetchJson(`/api/label/${encodeURIComponent(image.name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state.currentDoc),
  });
  state.images[state.currentIndex].label_exists = true;
  renderImageList();
  setStatus(`Saved ${image.name}`);
}

async function resetAnnotations() {
  if (!state.currentDoc || state.currentIndex < 0) {
    return;
  }
  const image = state.images[state.currentIndex];
  const confirmed = window.confirm(
    `Reset annotations for ${image.name}? This will discard manual edits, merges, deletes, labels, and added boxes for the current page.`,
  );
  if (!confirmed) {
    return;
  }

  const freshDoc = await fetchJson(
    `/api/label/${encodeURIComponent(image.name)}?reload=1&rotation=${state.rotation}`,
  );
  state.currentDoc = freshDoc;
  state.rotation = Number(state.currentDoc.rotation || state.rotation) % 360;
  clearSelection();
  await saveCurrent();
  setStatus(`Reset annotations for ${image.name}`);
}

function moveImage(delta) {
  if (!state.images.length) return;
  const nextIndex = Math.max(0, Math.min(state.images.length - 1, state.currentIndex + delta));
  if (nextIndex !== state.currentIndex) {
    loadImage(nextIndex, false);
  }
}

function rotate(delta) {
  state.rotation = (state.rotation + delta + 360) % 360;
  if (state.currentDoc) {
    state.currentDoc.rotation = state.rotation;
  }
  updateStageTransform();
  setStatus(`Rotation ${state.rotation}\u00b0`);
}

async function handleStageClick(event) {
  if (state.selectBoxMode && state.currentDoc) {
    if (event.target.closest(".token-box")) {
      return;
    }
    const point = getViewPointFromClient(event.clientX, event.clientY);
    if (!point) {
      return;
    }
    if (!state.selectBoxStart) {
      state.selectBoxStart = point;
      state.selectBoxAppend = event.ctrlKey || event.metaKey;
      renderSelectionBox(point, point);
      setStatus("Box-select mode: click the opposite corner to finish selection");
      return;
    }
    const start = state.selectBoxStart;
    const appendSelection = state.selectBoxAppend;
    state.selectBoxStart = null;
    state.selectBoxAppend = false;
    hideSelectionBox();
    const rect = imageStage.getBoundingClientRect();
    const width = Math.abs(point.x - start.x) * rect.width;
    const height = Math.abs(point.y - start.y) * rect.height;
    if (width < 4 || height < 4) {
      setStatus("Box-select canceled: click two corners farther apart");
      return;
    }
    applyBoxSelection(start, point, appendSelection);
    return;
  }
  if (!state.addBoxMode || !state.currentDoc) {
    return;
  }
  if (event.target.closest(".token-box")) {
    return;
  }
  const point = getViewPointFromClient(event.clientX, event.clientY);
  if (!point) {
    return;
  }
  if (!state.draftBoxStart) {
    state.draftBoxStart = point;
    renderDraftBox(point, point);
    setStatus("Add-box mode: click the opposite corner to finish the box");
    return;
  }
  const start = state.draftBoxStart;
  state.draftBoxStart = null;
  hideDraftBox();
  const rect = imageStage.getBoundingClientRect();
  const width = Math.abs(point.x - start.x) * rect.width;
  const height = Math.abs(point.y - start.y) * rect.height;
  if (width < 6 || height < 6) {
    setStatus("Add-box canceled: click two corners farther apart");
    return;
  }
  const index = createTokenFromDraft(start, point);
  if (index !== null) {
    await runOCRForToken(index);
  }
}

function handlePointerMove(event) {
  if (state.selectBoxMode && state.selectBoxStart) {
    const point = getViewPointFromClient(event.clientX, event.clientY);
    if (!point) {
      return;
    }
    renderSelectionBox(state.selectBoxStart, point);
    return;
  }
  if (!state.addBoxMode || !state.draftBoxStart) {
    return;
  }
  const point = getViewPointFromClient(event.clientX, event.clientY);
  if (!point) {
    return;
  }
  renderDraftBox(state.draftBoxStart, point);
}

document.getElementById("refresh-images").addEventListener("click", loadImages);
document.getElementById("zoom-out").addEventListener("click", () => adjustZoom(-0.1));
document.getElementById("zoom-in").addEventListener("click", () => adjustZoom(0.1));
document.getElementById("zoom-reset").addEventListener("click", () => setZoom(1));
document.getElementById("toggle-select-box").addEventListener("click", () => toggleSelectBoxMode());
document.getElementById("toggle-add-box").addEventListener("click", () => toggleAddBoxMode());
document.getElementById("save-labels").addEventListener("click", saveCurrent);
document.getElementById("reset-annotations").addEventListener("click", resetAnnotations);
document.getElementById("merge-tokens").addEventListener("click", mergeSelectedTokens);
document.getElementById("delete-token").addEventListener("click", deleteSelectedToken);
document.getElementById("reload-ocr").addEventListener("click", () => loadImage(state.currentIndex, true));
document.getElementById("prev-image").addEventListener("click", () => moveImage(-1));
document.getElementById("next-image").addEventListener("click", () => moveImage(1));
document.getElementById("rotate-left").addEventListener("click", () => rotate(270));
document.getElementById("rotate-right").addEventListener("click", () => rotate(90));
tokenText.addEventListener("input", syncSelectedToken);
tokenLabel.addEventListener("change", syncSelectedToken);
showOLabels.addEventListener("change", renderBoxes);
imageStage.addEventListener("click", handleStageClick);
window.addEventListener("pointermove", handlePointerMove);
window.addEventListener("resize", renderBoxes);

document.addEventListener("keydown", (event) => {
  const editingField = document.activeElement === tokenText || document.activeElement === tokenLabel;
  if (!editingField && event.key === "Escape" && (state.addBoxMode || state.selectBoxMode)) {
    toggleAddBoxMode(false);
    toggleSelectBoxMode(false);
    setStatus("Tool mode disabled");
    return;
  }
  if (editingField) {
    return;
  }
  if (event.key.toLowerCase() === "v") {
    event.preventDefault();
    toggleSelectBoxMode();
    return;
  }
  if (event.key.toLowerCase() === "n") {
    event.preventDefault();
    toggleAddBoxMode();
    return;
  }
  if (event.key === "+" || event.key === "=") {
    event.preventDefault();
    adjustZoom(0.1);
    return;
  }
  if (event.key === "-") {
    event.preventDefault();
    adjustZoom(-0.1);
    return;
  }
  if (event.key === "0") {
    event.preventDefault();
    setZoom(1);
    return;
  }
  const step = event.altKey ? 10 : 2;
  if (event.key.startsWith("Arrow")) {
    event.preventDefault();
    if (event.shiftKey) {
      const [edge, delta] = mapViewResizeToDocument(event.key, step);
      resizeSelectedBBoxes(edge, delta);
      return;
    }
    if (event.ctrlKey || event.metaKey) {
      const [edge, delta] = mapViewResizeToDocument(event.key, -step);
      resizeSelectedBBoxes(edge, delta);
      return;
    }
    const deltas = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const [dx, dy] = mapViewDeltaToDocument(...deltas[event.key]);
    moveSelectedBBoxes(dx, dy);
    return;
  }
  if (event.key === "s") {
    event.preventDefault();
    saveCurrent();
    return;
  }
  if (event.key === "[") {
    moveImage(-1);
    return;
  }
  if (event.key === "]") {
    moveImage(1);
    return;
  }
  if (event.key === "q") {
    rotate(270);
    return;
  }
  if (event.key === "e") {
    rotate(90);
    return;
  }
  if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    deleteSelectedToken();
    return;
  }
  if (event.key.toLowerCase() === "m") {
    event.preventDefault();
    mergeSelectedTokens();
    return;
  }
  const index = Number(event.key) - 1;
  if (index >= 0 && index < LABELS.length && state.selectedToken >= 0) {
    tokenLabel.value = LABELS[index];
    syncSelectedToken();
  }
});

updateZoomUI();
loadImages().catch((error) => setStatus(error.message));
