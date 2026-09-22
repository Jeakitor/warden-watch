let socket = null;
let token = null;
let role = null;
let authenticated = false;

let reconnectTimer = null;
let reconnectDelay = 1000;
let manuallyDisconnected = false;


const EVENTS = {
    WARDEN_ENTERED: {
        icon: "🔴",
        title: "Warden entered",
        message: "Be alert",
        className: "alert-red"
    },

    WARDEN_STOOD_UP: {
        icon: "🟠",
        title: "Warden stood up",
        message: "Be prepared",
        className: "alert-orange"
    },

    WARDEN_LOOKING: {
        icon: "🟡",
        title: "Warden looking",
        message: "Stay sharp",
        className: "alert-yellow"
    },

    COAST_CLEAR: {
        icon: "🟢",
        title: "Coast clear",
        message: "Yay",
        className: "alert-green"
    },

    WARDEN_LEFT: {
        icon: "🟢",
        title: "Warden left",
        message: "Goon forth my children",
        className: "alert-green"
    }
};


const SHORTCUTS = {
    "1": "WARDEN_ENTERED",
    "2": "WARDEN_STOOD_UP",
    "3": "WARDEN_LOOKING",
    "4": "COAST_CLEAR",
    "5": "WARDEN_LEFT"
};


const statusElement = document.getElementById("status");
const connectionStatus = document.getElementById("connection-status");
const statusDot = document.getElementById("status-dot");

const roleStatus = document.getElementById("role-status");
const roleLabel = document.getElementById("role-label");

const tokenInput = document.getElementById("token");
const connectButton = document.getElementById("connect");
const errorElement = document.getElementById("error");

const loginSection = document.getElementById("login");
const clientSection = document.getElementById("client");
const lookoutSection = document.getElementById("lookout");

const alertDisplay = document.getElementById("alert-display");
const alertIcon = document.getElementById("alert-icon");
const alertTitle = document.getElementById("alert-title");
const alertMessage = document.getElementById("alert-message");

const lastAlert = document.getElementById("last-alert");
const lastAlertTitle = document.getElementById("last-alert-title");
const lastAlertTime = document.getElementById("last-alert-time");

const lastSent = document.getElementById("last-sent");
const lastSentTitle = document.getElementById("last-sent-title");
const lastSentTime = document.getElementById("last-sent-time");


function setStatus(text, state = "disconnected") {
    statusElement.textContent = text;

    connectionStatus.className = "";
    connectionStatus.classList.add(`status-${state}`);
}


function showError(text) {
    errorElement.textContent = text;
}


function showRole() {

    loginSection.classList.add("hidden");

    if (role === "client") {
        clientSection.classList.remove("hidden");
        lookoutSection.classList.add("hidden");
    }

    if (role === "lookout") {
        lookoutSection.classList.remove("hidden");
        clientSection.classList.add("hidden");
    }
}

function getCurrentTime() {

    return new Date().toLocaleTimeString(
        [],
        {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
        }
    );
}


function updateLastAlert(event) {

    const alert = EVENTS[event];

    if (!alert) {
        return;
    }

    lastAlertTitle.textContent = alert.title;
    lastAlertTime.textContent = getCurrentTime();

    lastAlert.classList.remove("hidden");
}


function updateLastSent(event) {

    const alert = EVENTS[event];

    if (!alert) {
        return;
    }

    lastSentTitle.textContent = alert.title;
    lastSentTime.textContent = getCurrentTime();

    lastSent.classList.remove("hidden");
}

function requestNotifications() {

    if (!("Notification" in window)) {
        return;
    }

    if (Notification.permission === "default") {
        Notification.requestPermission();
    }
}


function sendNotification(alert) {

    if (!("Notification" in window)) {
        return;
    }

    if (Notification.permission !== "granted") {
        return;
    }

    new Notification(alert.title, {
        body: alert.message,
        icon: "/static/icon.svg"
    });
}

function displayAlert(event) {

    const alert = EVENTS[event];

    if (!alert) {
        return;
    }

    updateLastAlert(event);

    alertDisplay.className = "";
    alertDisplay.classList.add(alert.className);
    alertDisplay.classList.add("alert-active");

    alertIcon.textContent = alert.icon;
    alertTitle.textContent = alert.title;
    alertMessage.textContent = alert.message;

    sendNotification(alert);
}



function getWebSocketURL() {

    const protocol =
    window.location.protocol === "https:"
    ? "wss:"
    : "ws:";

    return `${protocol}//${window.location.host}/ws`;
}


function scheduleReconnect() {

    if (manuallyDisconnected) {
        return;
    }

    if (reconnectTimer !== null) {
        return;
    }

    setStatus(
        `Reconnecting in ${reconnectDelay / 1000}s...`,
        "reconnecting"
    );

    reconnectTimer = setTimeout(() => {

        reconnectTimer = null;

        connectSocket();

    }, reconnectDelay);

    reconnectDelay = Math.min(
        reconnectDelay * 2,
        30000
    );
}


function connectSocket() {

    if (!token) {
        return;
    }

    if (
        socket &&
        (
            socket.readyState === WebSocket.OPEN ||
            socket.readyState === WebSocket.CONNECTING
        )
    ) {
        return;
    }

    setStatus("Connecting...", "connecting");

    socket = new WebSocket(getWebSocketURL());

    socket.addEventListener("open", () => {

        setStatus("Authenticating...", "authenticating");

        socket.send(JSON.stringify({
            type: "auth",
            token: token
        }));

    });


    socket.addEventListener("message", event => {

        let data;

        try {
            data = JSON.parse(event.data);

        } catch {
            console.error("Invalid server message.");
            return;
        }


        if (data.type === "auth_result") {

            if (!data.success) {

                authenticated = false;

                setStatus(
                    "Authentication failed",
                    "disconnected"
                );

                showError(
                    data.reason || "Authentication failed."
                );

                manuallyDisconnected = true;

                socket.close();

                return;
            }

            role = data.role;
            authenticated = true;

            reconnectDelay = 1000;

            setStatus(
                role === "lookout"
                ? "Connected as lookout"
                : "Connected as client",
                "connected"
            );

            setRole(role);
            showRole();

            if (role === "client") {
                requestNotifications();
            }

            return;
        }


        if (data.type === "alert") {

            displayAlert(data.event);

        }

    });


    socket.addEventListener("close", () => {

        socket = null;
        authenticated = false;

        if (manuallyDisconnected) {

            setStatus(
                "Disconnected",
                "disconnected"
            );

            setRole(null);

            return;
        }

        setStatus(
            "Connection lost",
            "disconnected"
        );

        scheduleReconnect();

    });


    socket.addEventListener("error", () => {

        setStatus(
            "Connection error",
            "disconnected"
        );

    });
}


function setRole(role) {

    if (!role) {
        roleStatus.classList.add("hidden");
        roleLabel.textContent = "";
        return;
    }

    roleStatus.classList.remove("hidden");

    roleLabel.textContent =
    role === "lookout"
    ? "LOOKOUT"
    : "CLIENT";
}

function connect() {

    const enteredToken = tokenInput.value.trim();

    if (!enteredToken) {

        showError("Enter an access token.");

        return;
    }

    token = enteredToken;

    manuallyDisconnected = false;

    showError("");

    connectButton.disabled = true;

    connectSocket();

}


function sendAlert(event) {

    if (
        !socket ||
        socket.readyState !== WebSocket.OPEN ||
        !authenticated
    ) {

        setStatus(
            "Not connected.",
            "disconnected"
        );

        return;
    }

    socket.send(JSON.stringify({
        type: "alert",
        event: event
    }));

    updateLastSent(event);

    /*
     * Give the lookout immediate feedback.
     */
    const button = document.querySelector(
        `[data-event="${event}"]`
    );

    if (button) {

        button.classList.remove("sent");

        void button.offsetWidth;

        button.classList.add("sent");

    }

}


connectButton.addEventListener(
    "click",
    connect
);


tokenInput.addEventListener(
    "keydown",
    event => {

        if (event.key === "Enter") {
            connect();
        }

    }
);


/*
 * Add keyboard shortcuts to lookout buttons.
 */
document
.querySelectorAll("#lookout button")
.forEach(button => {

    const event = button.dataset.event;

    const shortcut = Object.entries(SHORTCUTS)
    .find(([, value]) => value === event);

    if (shortcut) {

        const badge = document.createElement("span");

        badge.className = "shortcut";
        badge.textContent = shortcut[0];

        button.prepend(badge);

    }

    button.addEventListener("click", () => {

        sendAlert(event);

    });

});


/*
 * Global lookout keyboard controls.
 */
document.addEventListener(
    "keydown",
    event => {

        if (role !== "lookout") {
            return;
        }

        /*
         * Don't trigger shortcuts while typing.
         */
        if (
            event.target.tagName === "INPUT" ||
            event.target.tagName === "TEXTAREA"
        ) {
            return;
        }

        const selected = SHORTCUTS[event.key];

        if (!selected) {
            return;
        }

        sendAlert(selected);

    }
);
