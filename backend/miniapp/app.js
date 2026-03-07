/**
 * Telegram Mini App -- Links to EPUB
 * Settings, History, and Subscription management.
 */

/* ===== i18n (loaded via i18n.js, included before app.js) ===== */
var t = i18n.t;

/* ===== App State ===== */
const state = {
  initData: "",
  user: null,
  settings: null,
  historyCursor: null,
  historyLoading: false,
  historyDone: false,
};

/* ===== Telegram WebApp ===== */
const tg = window.Telegram.WebApp;

/* ===== DOM helpers ===== */
function $(id) {
  return document.getElementById(id);
}

function show(el) {
  el.style.display = "";
}

function hide(el) {
  el.style.display = "none";
}

function el(tag, attrs, children) {
  const node = document.createElement(tag);
  if (attrs) {
    Object.keys(attrs).forEach(function (key) {
      if (key === "className") {
        node.className = attrs[key];
      } else if (key.startsWith("on")) {
        node.addEventListener(key.slice(2).toLowerCase(), attrs[key]);
      } else {
        node.setAttribute(key, attrs[key]);
      }
    });
  }
  if (children !== undefined) {
    if (typeof children === "string") {
      node.textContent = children;
    } else if (Array.isArray(children)) {
      children.forEach(function (child) {
        if (child) node.appendChild(child);
      });
    }
  }
  return node;
}

/* ===== Toast ===== */
var toastTimer = null;
function showToast(message) {
  var toast = $("toast");
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () {
    toast.classList.remove("visible");
  }, 2500);
}

/* ===== API helper ===== */
var API_BASE = "/api/miniapp";

function api(method, path, body) {
  var opts = {
    method: method,
    headers: {
      "Content-Type": "application/json",
      Authorization: state.initData,
    },
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  return fetch(API_BASE + path, opts).then(function (res) {
    if (!res.ok) {
      return res.json().catch(function () { return {}; }).then(function (errData) {
        throw new Error(errData.detail || "HTTP " + res.status);
      });
    }
    return res.json();
  });
}

/* ===== Populate i18n text ===== */
function populateText() {
  $("tab-settings").textContent = t("tabs.settings");
  $("tab-history").textContent = t("tabs.history");
  $("tab-subscription").textContent = t("tabs.subscription");

  $("label-settings-header").textContent = t("settings.header");
  $("label-kindle-email").textContent = t("settings.kindle_email_label");
  $("kindle-email").placeholder = t("settings.kindle_email_placeholder");
  $("hint-kindle-email").textContent = t("settings.kindle_email_hint");
  $("error-kindle-email").textContent = t("settings.kindle_email_error");
  $("label-grayscale").textContent = t("settings.grayscale_label");
  $("hint-grayscale").textContent = t("settings.grayscale_hint");
  $("btn-save-settings").textContent = t("settings.save_button");

  $("label-history-header").textContent = t("history.header");
  $("label-history-empty").textContent = t("history.empty");

  $("label-sub-header").textContent = t("subscription.header");
}

/* ===== Tab switching ===== */
function initTabs() {
  var buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      switchTab(btn.dataset.tab);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(function (b) {
    b.classList.remove("active");
  });
  document.querySelectorAll(".tab-panel").forEach(function (p) {
    p.classList.remove("active");
  });

  $("tab-" + tabId).classList.add("active");
  $("panel-" + tabId).classList.add("active");

  if (tabId === "history" && $("history-list").children.length === 0 && !state.historyDone) {
    loadHistory();
  }
  if (tabId === "subscription") {
    loadSubscription();
  }
}

/* ===== Kindle email validation ===== */
function validateKindleEmail(email) {
  if (!email || email.trim() === "") return true;
  var lower = email.trim().toLowerCase();
  return lower.endsWith("@kindle.com") || lower.endsWith("@free.kindle.com");
}

/* ===== Settings ===== */
function loadSettings() {
  return api("GET", "/settings").then(function (data) {
    state.settings = data;
    $("kindle-email").value = data.kindle_email || "";
    $("grayscale-toggle").checked = data.grayscale_images;
    $("btn-save-settings").disabled = false;
  }).catch(function () {
    showToast(t("settings.save_error"));
  });
}

function saveSettings() {
  var emailInput = $("kindle-email");
  var email = emailInput.value.trim();
  var errorEl = $("error-kindle-email");

  if (!validateKindleEmail(email)) {
    emailInput.classList.add("error");
    show(errorEl);
    return;
  }
  emailInput.classList.remove("error");
  hide(errorEl);

  var btn = $("btn-save-settings");
  btn.disabled = true;

  api("PUT", "/settings", {
    kindle_email: email || null,
    grayscale_images: $("grayscale-toggle").checked,
  }).then(function (data) {
    state.settings = data;
    showToast(t("settings.save_success"));
    tg.HapticFeedback.notificationOccurred("success");
  }).catch(function () {
    showToast(t("settings.save_error"));
    tg.HapticFeedback.notificationOccurred("error");
  }).finally(function () {
    btn.disabled = false;
  });
}

/* ===== History ===== */
function formatDate(isoString) {
  var date = new Date(isoString);
  var now = new Date();
  var diffMs = now - date;
  var diffDays = Math.floor(diffMs / 86400000);

  if (diffDays === 0) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return date.toLocaleDateString([], { weekday: "short" });
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function formatSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function createHistoryItem(item) {
  var title = item.title || t("history.untitled");
  var sizeStr = formatSize(item.file_size_bytes);

  var metaChildren = [
    el("span", { className: "history-item-date" }, formatDate(item.created_at)),
  ];
  if (sizeStr) {
    metaChildren.push(el("span", { className: "history-item-size" }, sizeStr));
  }

  var contentDiv = el("div", { className: "history-item-content" }, [
    el("a", {
      className: "history-item-title",
      href: item.url,
      target: "_blank",
      rel: "noopener",
    }, title),
    el("div", { className: "history-item-url" }, item.url),
    el("div", { className: "history-item-meta" }, metaChildren),
  ]);

  var badge = el("span", { className: "status-badge " + item.status }, item.status);

  return el("li", { className: "history-item" }, [contentDiv, badge]);
}

function loadHistory() {
  if (state.historyLoading || state.historyDone) return;
  state.historyLoading = true;

  var spinner = $("history-spinner");
  var emptyState = $("history-empty");
  show(spinner);

  var url = "/history?limit=20";
  if (state.historyCursor) {
    url += "&cursor=" + encodeURIComponent(state.historyCursor);
  }

  api("GET", url).then(function (data) {
    var list = $("history-list");

    data.items.forEach(function (item) {
      list.appendChild(createHistoryItem(item));
    });

    state.historyCursor = data.next_cursor;
    if (!data.next_cursor) {
      state.historyDone = true;
    }

    if (list.children.length === 0) {
      show(emptyState);
    } else {
      hide(emptyState);
    }
  }).catch(function () {
    showToast(t("history.load_error"));
  }).finally(function () {
    state.historyLoading = false;
    hide(spinner);
  });
}

/* Infinite scroll for history */
function initHistoryScroll() {
  window.addEventListener("scroll", function () {
    if (!$("panel-history").classList.contains("active")) return;
    if (state.historyLoading || state.historyDone) return;

    var scrollBottom = window.innerHeight + window.scrollY;
    var docHeight = document.documentElement.scrollHeight;

    if (docHeight - scrollBottom < 200) {
      loadHistory();
    }
  });
}

/* ===== Subscription ===== */
function loadSubscription() {
  var card = $("sub-card");
  /* Clear previous content and show spinner */
  while (card.firstChild) card.removeChild(card.firstChild);
  card.appendChild(el("div", { className: "spinner" }));

  api("GET", "/subscription").then(function (data) {
    renderSubscription(data);
  }).catch(function () {
    showToast(t("subscription.load_error"));
    while (card.firstChild) card.removeChild(card.firstChild);
  });
}

function renderSubscription(data) {
  var card = $("sub-card");
  var isPro = data.is_subscribed;

  while (card.firstChild) card.removeChild(card.firstChild);

  var planName, detail;

  if (isPro) {
    planName = t("subscription.pro_plan");
    var endDate = data.current_period_end
      ? new Date(data.current_period_end).toLocaleDateString([], {
          year: "numeric",
          month: "long",
          day: "numeric",
        })
      : "";
    detail = t("subscription.pro_active_until", { date: endDate });
  } else {
    planName = t("subscription.free_plan");
    detail = t("subscription.free_usage", {
      used: data.total_conversions,
      limit: data.free_tier_limit,
    });
  }

  card.appendChild(el("div", { className: "sub-plan" }, planName));
  card.appendChild(el("div", { className: "sub-detail" }, detail));

  if (!isPro) {
    var usagePercent = Math.min(100, (data.total_conversions / data.free_tier_limit) * 100);
    var barClass = "usage-bar";
    if (usagePercent >= 100) barClass += " full";
    else if (usagePercent >= 80) barClass += " warning";

    var usageBar = el("div", { className: barClass });
    usageBar.style.width = usagePercent + "%";

    var barContainer = el("div", { className: "usage-bar-container" }, [usageBar]);
    var usageDiv = el("div", { className: "sub-usage" }, [barContainer]);
    card.appendChild(usageDiv);

    var subBtn = el("button", {
      className: "btn-primary",
      onClick: handleSubscribe,
    }, t("subscription.subscribe_button"));

    var btnWrapper = el("div", { className: "sub-btn" }, [subBtn]);
    card.appendChild(btnWrapper);
  }
}

function handleSubscribe() {
  /* Deep link to bot with /subscribe command */
  var botData = tg.initDataUnsafe && tg.initDataUnsafe.bot;
  var botUsername = botData ? botData.username : null;
  if (botUsername) {
    tg.openTelegramLink("https://t.me/" + botUsername + "?start=subscribe");
  }
  tg.close();
}

/* ===== Email input live validation ===== */
function initEmailValidation() {
  var emailInput = $("kindle-email");
  emailInput.addEventListener("input", function () {
    var val = emailInput.value.trim();
    if (val === "" || validateKindleEmail(val)) {
      emailInput.classList.remove("error");
      hide($("error-kindle-email"));
    }
  });

  emailInput.addEventListener("blur", function () {
    var val = emailInput.value.trim();
    if (val !== "" && !validateKindleEmail(val)) {
      emailInput.classList.add("error");
      show($("error-kindle-email"));
    }
  });
}

/* ===== Initialization ===== */
function init() {
  tg.ready();
  tg.expand();

  /* Detect user locale from Telegram WebApp data */
  var userData = tg.initDataUnsafe && tg.initDataUnsafe.user;
  var userLocale = (userData && userData.language_code) || "en";

  /* Load i18n strings, then populate UI */
  i18n.load(userLocale).then(function () {
    t = i18n.t;
    populateText();
    initTabs();
    initHistoryScroll();
    initEmailValidation();

    state.initData = tg.initData;

    /* Save button handler */
    $("btn-save-settings").addEventListener("click", saveSettings);

    /* Authenticate */
    api("POST", "/auth", { init_data: tg.initData }).then(function (authData) {
      state.user = authData;

      var name = authData.first_name || authData.username || "";
      $("welcome-text").textContent = t("welcome", { name: name });

      /* Load settings right away (we start on settings tab) */
      return loadSettings();
    }).catch(function () {
      showToast(t("error_auth"));
    });
  });
}

init();
