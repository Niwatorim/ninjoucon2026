const TRAINING_SOCKET_URL = "ws://localhost:8765";
const CONTENT_READY_MESSAGE = "MOTIONLEARN_CONTENT_READY";
const registeredTabIds = new Set();

let socket = null;
let reconnectTimer = null;

function isSocketActive() {
    return socket && (
        socket.readyState === WebSocket.OPEN ||
        socket.readyState === WebSocket.CONNECTING
    );
}

function clearReconnectTimer() {
    if (!reconnectTimer) return;
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
}

function scheduleReconnect(delayMs = 3000) {
    if (reconnectTimer) return;

    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
    }, delayMs);
}

function sendMessageToTab(tabId, data) {
    chrome.tabs.sendMessage(tabId, data, () => {
        if (!chrome.runtime.lastError) return;

        registeredTabIds.delete(tabId);
        if (data.type !== "OPENCV_FRAME") {
            console.warn(
                `MotionLearn relay could not deliver ${data.action || data.type} to tab ${tabId}:`,
                chrome.runtime.lastError.message
            );
        }
    });
}

function queryYouTubeTabsAndSend(data) {
    chrome.tabs.query({ url: "https://www.youtube.com/*" }, (tabs) => {
        if (chrome.runtime.lastError) {
            console.warn("MotionLearn relay could not query YouTube tabs:", chrome.runtime.lastError.message);
            return;
        }

        tabs.forEach((tab) => {
            if (typeof tab.id !== "number") return;

            registeredTabIds.add(tab.id);
            sendMessageToTab(tab.id, data);
        });
    });
}

function forwardToContentScripts(data) {
    if (registeredTabIds.size === 0) {
        queryYouTubeTabsAndSend(data);
        return;
    }

    Array.from(registeredTabIds).forEach((tabId) => {
        sendMessageToTab(tabId, data);
    });
}

function connectWebSocket() {
    if (isSocketActive()) return;

    clearReconnectTimer();
    socket = new WebSocket(TRAINING_SOCKET_URL);

    socket.onopen = () => {
        console.log("Opened MotionLearn training websocket");
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type !== "OPENCV_FRAME") {
            console.log("MotionLearn relay received:", data.action || data.type);
        }

        forwardToContentScripts(data);
    };

    socket.onclose = () => {
        console.log("Closed MotionLearn training websocket");
        socket = null;
        scheduleReconnect();
    };

    socket.onerror = (error) => {
        console.error("MotionLearn training websocket error:", error);
        if (socket) {
            socket.close();
        }
    };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const senderTabId = sender.tab && sender.tab.id;

    if (message && message.type === CONTENT_READY_MESSAGE) {
        if (typeof senderTabId === "number") {
            registeredTabIds.add(senderTabId);
        }

        connectWebSocket();
        sendResponse({
            ok: true,
            socketState: socket ? socket.readyState : WebSocket.CLOSED
        });
        return false;
    }

    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(message));
    } else {
        connectWebSocket();
        if (message && message.type !== "TIME_UPDATE") {
            console.warn("MotionLearn relay dropped message while websocket was not open:", message.type);
        }
    }

    return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
    registeredTabIds.delete(tabId);
});

connectWebSocket();
