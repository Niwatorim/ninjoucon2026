/*
Await input
python ->
Seek to that value
*/

console.log("Content.js loaded");

const WEBCAM_OVERLAY_ID = "motionlearn-webcam-overlay";
let overlayCheckTimer = null;
let overlayExpanded = false;

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
        button.textContent = expanded ? "Collapse" : "Expand";
        button.setAttribute("aria-pressed", String(expanded));
        button.setAttribute("aria-label", expanded ? "Collapse webcam overlay" : "Expand webcam overlay");
        setStyles(button, (fullscreen || expanded) ? {
            padding: "5px 10px",
            fontSize: "13px"
        } : {
            padding: "3px 7px",
            fontSize: "11px"
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
    expandButton.setAttribute("aria-label", "Expand webcam overlay");
    setStyles(expandButton, {
        appearance: "none",
        border: "1px solid rgba(255, 255, 255, 0.72)",
        borderRadius: "4px",
        background: "rgba(255, 255, 255, 0.14)",
        color: "#ffffff",
        cursor: "pointer",
        fontFamily: "Arial, sans-serif",
        fontWeight: "700",
        lineHeight: "1.2",
        pointerEvents: "auto"
    });
    expandButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        overlayExpanded = !overlayExpanded;
        expandButton.setAttribute("aria-label", overlayExpanded ? "Collapse webcam overlay" : "Expand webcam overlay");
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
        ensureWebcamOverlay();
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
        ensureWebcamOverlay();
    }, { once: true });
} else {
    ensureWebcamOverlay();
}

document.addEventListener("yt-navigate-finish", scheduleOverlayCheck);
document.addEventListener("fullscreenchange", scheduleOverlayCheck);
document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !overlayExpanded) return;

    const overlay = document.getElementById(WEBCAM_OVERLAY_ID);
    overlayExpanded = false;
    if (overlay) {
        const button = overlay.querySelector("[data-motionlearn-expand-button='true']");
        if (button) {
            button.setAttribute("aria-label", "Expand webcam overlay");
        }
        applyOverlayLayout(overlay, getYouTubePlayer());
    }
});

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
