/*
Await input
python ->
Seek to that value
*/

console.log("Content.js loaded");

const WEBCAM_OVERLAY_ID = "motionlearn-webcam-overlay";
let webcamStream = null;
let webcamRequest = null;
let webcamErrorMessage = "";
let overlayCheckTimer = null;
let overlayCheckNeedsPreviewStart = false;

function getYouTubePlayer() {
    return document.querySelector("#movie_player") || document.querySelector(".html5-video-player");
}

function setStyles(element, styles) {
    Object.assign(element.style, styles);
}

function isYouTubeFullscreen(player) {
    return Boolean(
        document.fullscreenElement ||
        (player && player.classList.contains("ytp-fullscreen"))
    );
}

function applyOverlayLayout(overlay, player) {
    const fullscreen = isYouTubeFullscreen(player);
    const label = overlay.querySelector("[data-motionlearn-label='true']");
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    setStyles(overlay, fullscreen ? {
        top: "24px",
        right: "24px",
        width: "clamp(420px, 28vw, 520px)",
        border: "3px solid rgba(255, 255, 255, 0.85)",
        borderRadius: "5px",
        boxShadow: "0 12px 32px rgba(0, 0, 0, 0.45)"
    } : {
        top: "16px",
        right: "16px",
        width: "220px",
        border: "2px solid rgba(255, 255, 255, 0.8)",
        borderRadius: "4px",
        boxShadow: "0 8px 24px rgba(0, 0, 0, 0.35)"
    });

    if (label) {
        setStyles(label, fullscreen ? {
            padding: "8px 12px",
            fontSize: "18px"
        } : {
            padding: "5px 8px",
            fontSize: "12px"
        });
    }

    if (status) {
        setStyles(status, fullscreen ? {
            padding: "16px",
            minHeight: "96px",
            fontSize: "16px"
        } : {
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

    const label = document.createElement("div");
    label.textContent = "Webcam Overlay";
    label.dataset.motionlearnLabel = "true";
    setStyles(label, {
        fontWeight: "700",
        textShadow: "0 1px 2px rgba(0, 0, 0, 0.8)",
        background: "rgba(0, 0, 0, 0.45)"
    });

    const preview = document.createElement("video");
    preview.autoplay = true;
    preview.muted = true;
    preview.playsInline = true;
    setStyles(preview, {
        display: "block",
        width: "100%",
        aspectRatio: "16 / 9",
        background: "#111827",
        objectFit: "cover",
        transform: "scaleX(-1)"
    });

    const status = document.createElement("div");
    status.dataset.motionlearnStatus = "true";
    setStyles(status, {
        display: "none",
        padding: "10px",
        minHeight: "52px",
        background: "#111827",
        color: "#f9fafb"
    });

    overlay.appendChild(label);
    overlay.appendChild(preview);
    overlay.appendChild(status);

    return overlay;
}

function showWebcamError(overlay, message) {
    const preview = overlay.querySelector("video");
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    if (preview) {
        preview.style.display = "none";
    }
    if (status) {
        status.textContent = message;
        status.style.display = "block";
    }
}

function showWebcamStatus(overlay, message) {
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    if (status) {
        status.textContent = message;
        status.style.display = "block";
    }
}

async function startWebcamPreview(overlay) {
    const preview = overlay.querySelector("video");
    const status = overlay.querySelector("[data-motionlearn-status='true']");

    if (!preview) return;

    if (webcamErrorMessage) {
        showWebcamError(overlay, webcamErrorMessage);
        return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        webcamErrorMessage = "Camera preview is not available in this browser.";
        showWebcamError(overlay, webcamErrorMessage);
        return;
    }

    if (!webcamStream) {
        try {
            webcamRequest = webcamRequest || navigator.mediaDevices.getUserMedia({
                video: true,
                audio: false
            });
            webcamStream = await webcamRequest;
            webcamErrorMessage = "";
        } catch (error) {
            console.warn(
                "MotionLearn webcam access failed:",
                error && error.name,
                error && error.message,
                error
            );
            webcamRequest = null;
            webcamErrorMessage = "Camera unavailable. Allow camera access or close another app using it, then reload YouTube.";
            showWebcamError(overlay, webcamErrorMessage);
            return;
        }
    }

    if (preview.srcObject !== webcamStream) {
        preview.srcObject = webcamStream;
    }

    preview.style.display = "block";

    if (preview.paused || preview.readyState < 2) {
        try {
            await preview.play();
        } catch (error) {
            console.warn(
                "MotionLearn webcam preview playback failed:",
                error && error.name,
                error && error.message,
                error
            );
            showWebcamStatus(overlay, "Camera connected, but preview playback was interrupted. Reload YouTube if the preview stays blank.");
            return;
        }
    }

    if (status) {
        status.style.display = "none";
        status.textContent = "";
    }
}

function ensureWebcamOverlay(options = {}) {
    const shouldStartPreview = Boolean(options.startPreview);
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
    if (createdOverlay || shouldStartPreview) {
        startWebcamPreview(overlay);
    }
}

function scheduleOverlayCheck(options = {}) {
    overlayCheckNeedsPreviewStart = overlayCheckNeedsPreviewStart || Boolean(options.startPreview);

    if (overlayCheckTimer) return;

    overlayCheckTimer = window.setTimeout(() => {
        const shouldStartPreview = overlayCheckNeedsPreviewStart;
        overlayCheckTimer = null;
        overlayCheckNeedsPreviewStart = false;
        ensureWebcamOverlay({ startPreview: shouldStartPreview });
    }, 250);
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
        ensureWebcamOverlay({ startPreview: true });
    }, { once: true });
} else {
    ensureWebcamOverlay({ startPreview: true });
}

document.addEventListener("yt-navigate-finish", scheduleOverlayCheck);
document.addEventListener("fullscreenchange", scheduleOverlayCheck);

const playerObserver = new MutationObserver((mutations) => {
    const player = getYouTubePlayer();
    if (!player) return;

    const overlay = document.getElementById(WEBCAM_OVERLAY_ID);
    const overlayMissing = !overlay || overlay.parentElement !== player;
    const playerClassChanged = mutations.some((mutation) => (
        mutation.type === "attributes" &&
        mutation.attributeName === "class" &&
        mutation.target === player
    ));

    if (overlayMissing) {
        scheduleOverlayCheck({ startPreview: true });
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
