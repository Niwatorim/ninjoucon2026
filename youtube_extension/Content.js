/*
Await input
python ->
Seek to that value
*/

console.log("Content.js loaded");

const WEBCAM_OVERLAY_ID = "motionlearn-webcam-overlay";
const SEGMENT_OVERLAY_CONTAINER_ID = "segment-overlay-container";
const SEGMENT_BUTTON_CONTAINER_ID = "segment-btn-container";
const CHECKPOINT_SOCKET_URL = "ws://localhost:8000";
const CONTENT_READY_MESSAGE = "MOTIONLEARN_CONTENT_READY";
let overlayCheckTimer = null;
let overlayExpanded = false;
let segmentSliderResolvedUrl = null;

function getYouTubePlayer() {
    return document.querySelector("#movie_player") || document.querySelector(".html5-video-player");
}

function setStyles(element, styles) {
    Object.assign(element.style, styles);
}

function registerMotionLearnContentScript() {
    chrome.runtime.sendMessage({ type: CONTENT_READY_MESSAGE }, () => {
        if (chrome.runtime.lastError) {
            console.warn("MotionLearn relay registration failed:", chrome.runtime.lastError.message);
        }
    });
}

function setExpandButtonIcon(button, expanded) {
    button.innerHTML = (expanded ? `
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
            <path d="M4 14h6v6" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M20 10h-6V4" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M14 10l7-7" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
            <path d="M3 21l7-7" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
        </svg>
    ` : `
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
            <path d="M15 3h6v6" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M9 21H3v-6" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M21 3l-7 7" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
            <path d="M3 21l7-7" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round"/>
        </svg>
    `).trim();
    button.setAttribute("aria-pressed", String(expanded));
    button.setAttribute("aria-label", expanded ? "Collapse webcam overlay" : "Expand webcam overlay");
}

function isYouTubeFullscreen(player) {
    return Boolean(
        document.fullscreenElement ||
        (player && player.classList.contains("ytp-fullscreen"))
    );
}

function applyOverlayLayout(overlay, player) {
    const fullscreen = isYouTubeFullscreen(player);
    const expanded = overlayExpanded;
    const header = overlay.querySelector("[data-motionlearn-header='true']");
    const label = overlay.querySelector("[data-motionlearn-label='true']");
    const button = overlay.querySelector("[data-motionlearn-expand-button='true']");
    const preview = overlay.querySelector("[data-motionlearn-preview='true']");
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    setStyles(overlay, expanded ? {
        top: "0",
        right: "0",
        bottom: "0",
        left: "0",
        width: "100%",
        height: "100%",
        display: "block",
        flexDirection: "initial",
        background: "transparent",
        border: "none",
        borderRadius: "0",
        boxShadow: "none"
    } : fullscreen ? {
        top: "24px",
        right: "24px",
        bottom: "auto",
        left: "auto",
        width: "clamp(420px, 28vw, 520px)",
        height: "auto",
        display: "block",
        flexDirection: "initial",
        background: "rgba(8, 12, 24, 0.88)",
        border: "3px solid rgba(255, 255, 255, 0.85)",
        borderRadius: "5px",
        boxShadow: "0 12px 32px rgba(0, 0, 0, 0.45)"
    } : {
        top: "16px",
        right: "16px",
        bottom: "auto",
        left: "auto",
        width: "220px",
        height: "auto",
        display: "block",
        flexDirection: "initial",
        background: "rgba(8, 12, 24, 0.88)",
        border: "2px solid rgba(255, 255, 255, 0.8)",
        borderRadius: "4px",
        boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)"
    });

    if (header) {
        setStyles(header, expanded ? {
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            position: "absolute",
            top: "0",
            right: "0",
            left: "0",
            zIndex: "1",
            padding: "10px 12px",
            background: "rgba(0, 0, 0, 0.58)",
            pointerEvents: "none"
        } : fullscreen ? {
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "10px",
            position: "static",
            top: "auto",
            right: "auto",
            left: "auto",
            zIndex: "auto",
            padding: "8px 12px",
            background: "rgba(0, 0, 0, 0.45)",
            pointerEvents: "none"
        } : {
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "8px",
            position: "static",
            top: "auto",
            right: "auto",
            left: "auto",
            zIndex: "auto",
            padding: "5px 8px",
            background: "rgba(0, 0, 0, 0.45)",
            pointerEvents: "none"
        });
    }

    if (label) {
        setStyles(label, (fullscreen || expanded) ? {
            padding: "0",
            fontSize: "18px"
        } : {
            padding: "0",
            fontSize: "12px"
        });
    }

    if (button) {
        setExpandButtonIcon(button, expanded);
        setStyles(button, (fullscreen || expanded) ? {
            width: "32px",
            height: "32px"
        } : {
            width: "28px",
            height: "28px"
        });
    }

    if (preview) {
        setStyles(preview, expanded ? {
            position: "absolute",
            top: "0",
            right: "0",
            bottom: "0",
            left: "0",
            width: "100%",
            height: "100%",
            minHeight: "0",
            flex: "0 0 auto",
            aspectRatio: "auto",
            background: "transparent",
            objectFit: "contain",
            transform: "none",
            opacity: "0.55"
        } : {
            position: "static",
            top: "auto",
            right: "auto",
            bottom: "auto",
            left: "auto",
            width: "100%",
            height: "auto",
            minHeight: "0",
            flex: "0 0 auto",
            aspectRatio: "16 / 9",
            background: "#111827",
            objectFit: "cover",
            transform: "none",
            opacity: "1"
        });
    }

    if (status) {
        setStyles(status, expanded ? {
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            zIndex: "2",
            width: "min(520px, 80%)",
            padding: "16px",
            minHeight: "96px",
            fontSize: "16px"
        } : fullscreen ? {
            position: "static",
            top: "auto",
            left: "auto",
            transform: "none",
            zIndex: "auto",
            width: "auto",
            padding: "16px",
            minHeight: "96px",
            fontSize: "16px"
        } : {
            position: "static",
            top: "auto",
            left: "auto",
            transform: "none",
            zIndex: "auto",
            width: "auto",
            padding: "10px",
            minHeight: "52px",
            fontSize: "12px"
        });
    }
}

function createWebcamOverlay() {
    const overlay = document.createElement("div");
    overlay.id = WEBCAM_OVERLAY_ID;
    overlay.setAttribute("aria-label", "MotionLearn webcam overlay");
    setStyles(overlay, {
        position: "absolute",
        zIndex: "2147483647",
        background: "rgba(8, 12, 24, 0.88)",
        color: "#ffffff",
        fontFamily: "Arial, sans-serif",
        fontSize: "12px",
        lineHeight: "1.3",
        overflow: "hidden",
        pointerEvents: "none"
    });

    const header = document.createElement("div");
    header.dataset.motionlearnHeader = "true";

    const label = document.createElement("div");
    label.textContent = "Webcam Overlay";
    label.dataset.motionlearnLabel = "true";
    setStyles(label, {
        fontWeight: "700",
        textShadow: "0 1px 2px rgba(0, 0, 0, 0.8)"
    });

    const expandButton = document.createElement("button");
    expandButton.type = "button";
    expandButton.dataset.motionlearnExpandButton = "true";
    setStyles(expandButton, {
        appearance: "none",
        alignItems: "center",
        background: "rgba(8, 12, 24, 0.88)",
        border: "1px solid rgba(255, 255, 255, 0.22)",
        borderRadius: "6px",
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.18)",
        color: "#ffffff",
        cursor: "pointer",
        display: "inline-flex",
        justifyContent: "center",
        padding: "0",
        pointerEvents: "auto"
    });
    setExpandButtonIcon(expandButton, false);
    expandButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        overlayExpanded = !overlayExpanded;
        applyOverlayLayout(overlay, getYouTubePlayer());
    });

    header.appendChild(label);
    header.appendChild(expandButton);

    const preview = document.createElement("img");
    preview.alt = "OpenCV pose view";
    preview.dataset.motionlearnPreview = "true";
    setStyles(preview, {
        display: "none",
        width: "100%",
        aspectRatio: "16 / 9",
        background: "#111827",
        objectFit: "cover",
        transform: "none"
    });

    const status = document.createElement("div");
    status.dataset.motionlearnStatus = "true";
    status.textContent = "Waiting for OpenCV pose view...";
    setStyles(status, {
        display: "block",
        padding: "10px",
        minHeight: "52px",
        background: "#111827",
        color: "#f9fafb"
    });

    overlay.appendChild(header);
    overlay.appendChild(preview);
    overlay.appendChild(status);

    return overlay;
}

function showOpenCvStatus(overlay, message) {
    const preview = overlay.querySelector("[data-motionlearn-preview='true']");
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    if (preview) {
        preview.style.display = "none";
    }
    if (status) {
        status.textContent = message;
        status.style.display = "block";
    }
}

function showOpenCvFrame(image) {
    if (!image) return;

    ensureWebcamOverlay();

    const overlay = document.getElementById(WEBCAM_OVERLAY_ID);
    if (!overlay) return;

    const preview = overlay.querySelector("[data-motionlearn-preview='true']");
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    if (!preview) return;

    preview.src = `data:image/jpeg;base64,${image}`;
    preview.style.display = "block";
    if (status) {
        status.style.display = "none";
        status.textContent = "";
    }
}

function ensureWebcamOverlay() {
    const player = getYouTubePlayer();
    if (!player) return;

    if (getComputedStyle(player).position === "static") {
        player.style.position = "relative";
    }

    let overlay = document.getElementById(WEBCAM_OVERLAY_ID);
    let createdOverlay = false;

    if (!overlay) {
        overlay = createWebcamOverlay();
        createdOverlay = true;
    }

    if (overlay.parentElement !== player) {
        player.appendChild(overlay);
    }

    applyOverlayLayout(overlay, player);
    if (createdOverlay) {
        showOpenCvStatus(overlay, "Waiting for OpenCV pose view...");
    }
}

function scheduleOverlayCheck() {
    if (overlayCheckTimer) return;

    overlayCheckTimer = window.setTimeout(() => {
        overlayCheckTimer = null;
        ensureMotionLearnYouTubeUi();
    }, 250);
}

function isFiniteVideoDuration(video) {
    return video && Number.isFinite(video.duration) && video.duration > 0;
}

function formatCheckpointTime(value) {
    return `${value.toFixed(2)}s`;
}

function sendCheckpointMessage(message) {
    return new Promise((resolve, reject) => {
        const ws = new WebSocket(CHECKPOINT_SOCKET_URL);
        let settled = false;

        function settle(callback, value) {
            if (settled) return;
            settled = true;
            callback(value);
        }

        ws.addEventListener("open", () => {
            try {
                ws.send(message);
                ws.close();
                settle(resolve);
            } catch (error) {
                settle(reject, error);
            }
        });

        ws.addEventListener("error", (error) => {
            settle(reject, error);
        });

        ws.addEventListener("close", () => {
            if (!settled) {
                settle(reject, new Error("Checkpoint WebSocket closed before message was sent."));
            }
        });
    });
}

function createSegmentButton(text) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = text;
    setStyles(button, {
        backgroundColor: "rgba(8, 12, 24, 0.88)",
        backdropFilter: "blur(10px)",
        WebkitBackdropFilter: "blur(10px)",
        border: "1px solid rgba(255, 255, 255, 0.45)",
        color: "#ffffff",
        padding: "10px 16px",
        borderRadius: "20px",
        cursor: "pointer",
        fontFamily: "\"Roboto\", Arial, sans-serif",
        fontSize: "14px",
        fontWeight: "bold",
        boxShadow: "0 8px 20px rgba(0, 0, 0, 0.3)",
        transition: "all 0.2s ease",
        pointerEvents: "auto"
    });

    button.addEventListener("mouseenter", () => {
        button.style.backgroundColor = "rgba(17, 24, 39, 0.96)";
        button.style.transform = "scale(1.05)";
    });

    button.addEventListener("mouseleave", () => {
        button.style.backgroundColor = "rgba(8, 12, 24, 0.88)";
        button.style.transform = "scale(1)";
    });

    return button;
}

function applySegmentButtonLayout(buttonContainer, player) {
    const fullscreen = isYouTubeFullscreen(player);
    setStyles(buttonContainer, fullscreen ? {
        top: "24px",
        right: "calc(24px + clamp(420px, 28vw, 520px) + 16px)",
        left: "auto"
    } : {
        top: "16px",
        right: "248px",
        left: "auto"
    });
}

function updateSegmentMarkers(slider, primaryBar, timeLabel, ghostContainer, video) {
    const value = parseFloat(slider.value);
    const duration = video.duration;

    if (!Number.isFinite(value) || !isFiniteVideoDuration(video)) return;

    const percentage = (value / duration) * 100;
    primaryBar.style.left = `${percentage}%`;
    timeLabel.textContent = formatCheckpointTime(value);
    ghostContainer.textContent = "";

    if (value <= 1) return;

    for (let nextValue = value * 2; nextValue <= duration; nextValue += value) {
        const ghostBar = document.createElement("div");
        setStyles(ghostBar, {
            position: "absolute",
            width: "0",
            height: "0",
            borderLeft: "8px solid transparent",
            borderRight: "8px solid transparent",
            borderTop: "20px solid #ffffff",
            backgroundColor: "transparent",
            opacity: "0.4",
            left: `${(nextValue / duration) * 100}%`,
            transform: "translateX(-50%)"
        });
        ghostContainer.appendChild(ghostBar);
    }
}

function removeSegmentSlider() {
    const container = document.getElementById(SEGMENT_OVERLAY_CONTAINER_ID);
    const buttonContainer = document.getElementById(SEGMENT_BUTTON_CONTAINER_ID);

    if (container) container.remove();
    if (buttonContainer) buttonContainer.remove();
}

function isYouTubeAdShowing(player) {
    if (!player) return false;

    if (
        player.classList.contains("ad-showing") ||
        player.classList.contains("ad-interrupting") ||
        player.classList.contains("ytp-ad-showing")
    ) {
        return true;
    }

    return Array.from(player.querySelectorAll(
        ".ytp-ad-player-overlay, .ytp-ad-module, .video-ads .ytp-ad-overlay-container"
    )).some((element) => {
        const styles = getComputedStyle(element);
        return (
            styles.display !== "none" &&
            styles.visibility !== "hidden" &&
            styles.opacity !== "0" &&
            element.getClientRects().length > 0 &&
            (element.children.length > 0 || element.textContent.trim())
        );
    });
}

function isCheckpointSelectionPending(video) {
    const container = document.getElementById(SEGMENT_OVERLAY_CONTAINER_ID);
    return Boolean(
        video &&
        container &&
        container.motionlearnVideoElement === video &&
        segmentSliderResolvedUrl !== location.href
    );
}

function attachCheckpointSelectionPauseGuard(video) {
    if (video.dataset.motionlearnCheckpointPauseGuard === "true") return;

    video.addEventListener("play", () => {
        if (isCheckpointSelectionPending(video) && !isYouTubeAdShowing(getYouTubePlayer())) {
            video.pause();
        }
    });
    video.addEventListener("playing", () => {
        if (isCheckpointSelectionPending(video) && !isYouTubeAdShowing(getYouTubePlayer())) {
            video.pause();
        }
    });
    video.dataset.motionlearnCheckpointPauseGuard = "true";
}

function resolveCheckpointSelection(video) {
    segmentSliderResolvedUrl = location.href;
    removeSegmentSlider();
    video.pause();
}

function setCheckpointSelectionPending(buttonContainer, isPending) {
    buttonContainer.querySelectorAll("button").forEach((button) => {
        button.disabled = isPending;
        button.style.opacity = isPending ? "0.65" : "1";
        button.style.cursor = isPending ? "wait" : "pointer";
    });
}

async function submitCheckpointSelection(message, video, buttonContainer, onSent) {
    video.pause();
    setCheckpointSelectionPending(buttonContainer, true);

    try {
        await sendCheckpointMessage(message);
        resolveCheckpointSelection(video);
        registerMotionLearnContentScript();
        if (onSent) onSent();
    } catch (error) {
        video.pause();
        console.error("Checkpoint WebSocket Error:", error);
    } finally {
        if (buttonContainer.isConnected) {
            setCheckpointSelectionPending(buttonContainer, false);
        }
    }
}

function createSegmentSlider(player, playerControls, video) {
    attachCheckpointSelectionPauseGuard(video);
    video.pause();

    const container = document.createElement("div");
    container.id = SEGMENT_OVERLAY_CONTAINER_ID;
    container.motionlearnVideoElement = video;
    setStyles(container, {
        position: "absolute",
        bottom: "55px",
        width: "100%",
        height: "30px",
        pointerEvents: "none",
        zIndex: "2147483646"
    });

    const ghostContainer = document.createElement("div");
    setStyles(ghostContainer, {
        position: "absolute",
        width: "100%",
        height: "100%"
    });

    const primaryBar = document.createElement("div");
    setStyles(primaryBar, {
        position: "absolute",
        width: "0",
        height: "0",
        borderLeft: "8px solid transparent",
        borderRight: "8px solid transparent",
        borderTop: "20px solid #ffffff",
        backgroundColor: "transparent",
        left: "0%",
        transform: "translateX(-50%)"
    });

    const timeLabel = document.createElement("div");
    timeLabel.textContent = "0.00s";
    setStyles(timeLabel, {
        position: "absolute",
        top: "-50px",
        left: "50%",
        transform: "translateX(-50%)",
        backgroundColor: "rgba(0, 0, 0, 0.7)",
        color: "#ffffff",
        padding: "4px 8px",
        borderRadius: "4px",
        fontSize: "12px",
        fontFamily: "monospace",
        whiteSpace: "nowrap"
    });
    primaryBar.appendChild(timeLabel);

    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "0";
    slider.max = String(video.duration);
    slider.value = "0";
    setStyles(slider, {
        position: "absolute",
        width: "100%",
        height: "100%",
        top: "0",
        left: "0",
        margin: "0",
        opacity: "0",
        cursor: "ew-resize",
        pointerEvents: "auto"
    });

    slider.addEventListener("input", () => {
        updateSegmentMarkers(slider, primaryBar, timeLabel, ghostContainer, video);
    });

    video.addEventListener("durationchange", () => {
        if (!isFiniteVideoDuration(video)) return;

        slider.max = String(video.duration);
        updateSegmentMarkers(slider, primaryBar, timeLabel, ghostContainer, video);
    });

    const buttonContainer = document.createElement("div");
    buttonContainer.id = SEGMENT_BUTTON_CONTAINER_ID;
    setStyles(buttonContainer, {
        position: "absolute",
        zIndex: "2147483646",
        display: "flex",
        gap: "10px",
        pointerEvents: "auto"
    });
    applySegmentButtonLayout(buttonContainer, player);

    const saveButton = createSegmentButton("Save Checkpoint");
    saveButton.addEventListener("click", () => {
        const value = parseFloat(slider.value).toFixed(2);
        submitCheckpointSelection(value, video, buttonContainer, () => {
            navigator.clipboard.writeText(value).then(() => {
                console.log(`Copied checkpoint time: ${value}s`);
            }).catch((error) => {
                console.error("Could not copy checkpoint time:", error);
            });
        });
    });

    const closeButton = createSegmentButton("X");
    closeButton.setAttribute("aria-label", "Cancel checkpoint selection");
    closeButton.addEventListener("click", () => {
        submitCheckpointSelection("no", video, buttonContainer);
    });

    buttonContainer.appendChild(saveButton);
    buttonContainer.appendChild(closeButton);

    container.appendChild(ghostContainer);
    container.appendChild(primaryBar);
    container.appendChild(slider);

    playerControls.appendChild(container);
    player.appendChild(buttonContainer);
}

function ensureSegmentSlider() {
    if (segmentSliderResolvedUrl === location.href) return;

    const player = getYouTubePlayer();
    const playerControls = document.querySelector(".ytp-chrome-bottom");
    const video = document.querySelector("video");

    if (!player || !playerControls || !video) return;

    if (isYouTubeAdShowing(player)) {
        return;
    }

    if (getComputedStyle(player).position === "static") {
        player.style.position = "relative";
    }

    if (!isFiniteVideoDuration(video)) {
        if (video.dataset.motionlearnSegmentMetadataListener !== "true") {
            video.dataset.motionlearnSegmentMetadataListener = "true";
            video.addEventListener("loadedmetadata", scheduleOverlayCheck, { once: true });
        }
        return;
    }

    const existingContainer = document.getElementById(SEGMENT_OVERLAY_CONTAINER_ID);
    const existingButtons = document.getElementById(SEGMENT_BUTTON_CONTAINER_ID);
    const alreadyAttached = (
        existingContainer &&
        existingContainer.parentElement === playerControls &&
        existingContainer.motionlearnVideoElement === video &&
        existingButtons &&
        existingButtons.parentElement === player
    );

    if (alreadyAttached) return;

    removeSegmentSlider();
    createSegmentSlider(player, playerControls, video);
}

function ensureMotionLearnYouTubeUi() {
    ensureWebcamOverlay();
    ensureSegmentSlider();

    const player = getYouTubePlayer();
    const buttonContainer = document.getElementById(SEGMENT_BUTTON_CONTAINER_ID);
    if (player && buttonContainer) {
        applySegmentButtonLayout(buttonContainer, player);
    }
}

function attachTimeUpdateListener(video) {
    if (video.dataset.motionlearnTimeListenerAttached === "true") return;

    video.addEventListener("timeupdate", () => {
        chrome.runtime.sendMessage({
            type: "TIME_UPDATE",
            currentTime: video.currentTime
        });
    });
    video.dataset.motionlearnTimeListenerAttached = "true";
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        ensureMotionLearnYouTubeUi();
        registerMotionLearnContentScript();
    }, { once: true });
} else {
    ensureMotionLearnYouTubeUi();
    registerMotionLearnContentScript();
}

document.addEventListener("yt-navigate-finish", () => {
    registerMotionLearnContentScript();
    scheduleOverlayCheck();
});
document.addEventListener("fullscreenchange", scheduleOverlayCheck);
document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !overlayExpanded) return;

    const overlay = document.getElementById(WEBCAM_OVERLAY_ID);
    overlayExpanded = false;
    if (overlay) {
        const button = overlay.querySelector("[data-motionlearn-expand-button='true']");
        if (button) {
            setExpandButtonIcon(button, false);
        }
        applyOverlayLayout(overlay, getYouTubePlayer());
    }
});

const playerObserver = new MutationObserver((mutations) => {
    const player = getYouTubePlayer();
    if (!player) return;

    const overlay = document.getElementById(WEBCAM_OVERLAY_ID);
    const segmentContainer = document.getElementById(SEGMENT_OVERLAY_CONTAINER_ID);
    const segmentButtons = document.getElementById(SEGMENT_BUTTON_CONTAINER_ID);
    const overlayMissing = !overlay || overlay.parentElement !== player;
    const segmentSliderResolved = segmentSliderResolvedUrl === location.href;
    const segmentSliderMissing = !segmentSliderResolved && (!segmentContainer || !segmentButtons);
    const playerClassChanged = mutations.some((mutation) => (
        mutation.type === "attributes" &&
        mutation.attributeName === "class" &&
        mutation.target === player
    ));

    if (overlayMissing || segmentSliderMissing) {
        scheduleOverlayCheck();
    } else if (playerClassChanged) {
        scheduleOverlayCheck();
    }
});

playerObserver.observe(document.documentElement, {
    attributes: true,
    childList: true,
    subtree: true,
    attributeFilter: ["class"]
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === "OPENCV_FRAME") {
        showOpenCvFrame(request.image);
        return;
    }

    console.log("Content Script command: ", request.action);
    console.log("Time to turn: ", request.seek_time);

    const video = document.querySelector("video");
    if (!video) return;

    attachTimeUpdateListener(video);

    if (request.action == "pause") video.pause();
    if (request.action == "seek") video.currentTime = request.seek_time;
    if (request.action == "play") video.play();
    if (request.action == "mini_seek") video.currentTime += request.seek_time;

    if (request.action == "play_until") {
        video.play();

        function checkTime() {
            if (video.currentTime >= request.target_time) {
                video.pause();
                video.currentTime = request.target_time;
                console.log(`Reached time, pausing video at ${request.target_time}`);
                chrome.runtime.sendMessage({ type: "ARRIVED" });
            } else {
                requestAnimationFrame(checkTime);
            }
        }
        requestAnimationFrame(checkTime);
    }
});
