(() => {
  const { $, el, pill, api, refreshJourneyAlerts } = window.hamarNotificationSupport;
  const key = "hamar-access-lab.notifications.v1";
  const dialog = $("notifications-dialog");
  const button = $("notifications-button");
  const status = $("city-notice-status");
  const followHamar = $("follow-hamar");
  const followJourneys = $("follow-journeys");
  const preferences = { hamar: true, journeys: true, read: [], dismissed: [] };
  let notices = [];
  let loading = false;
  let unavailable = false;
  let ready = false;
  const labels = {
    works_scheduled: "Scheduled works",
    works_upcoming: "Upcoming works",
    works_started: "Reported works start",
    closure_announced: "Announced closure",
    closure_active: "Reported active closure",
    reopened: "Reopening confirmed",
    walking: "Walking",
    driving: "Driving",
  };

  try {
    const saved = JSON.parse(localStorage.getItem(key));
    for (const scope of ["hamar", "journeys"]) {
      if (typeof saved?.[scope] === "boolean") preferences[scope] = saved[scope];
    }
    for (const state of ["read", "dismissed"]) {
      if (Array.isArray(saved?.[state])) {
        preferences[state] = saved[state].filter((id) => typeof id === "string");
      }
    }
  } catch {
    $("notification-storage-status").textContent = "Browser notification preferences could not be loaded.";
  }
  followHamar.checked = preferences.hamar;
  followJourneys.checked = preferences.journeys;

  function save() {
    try {
      localStorage.setItem(key, JSON.stringify(preferences));
      $("notification-storage-status").textContent = "";
    } catch {
      $("notification-storage-status").textContent = "Browser notification preferences could not be saved.";
    }
  }

  function period(item) {
    return [item.start_date, item.end_date].filter(Boolean).join(" – ") || item.period;
  }

  function evidenceBlock(revision) {
    const kind = revision.evidence_kind;
    return el("div", {},
      el("p", { class: "hint" }, kind === "quote" ? "Source quotation" : kind === "summary" ? "Source summary" : "Source note"),
      el(kind === "quote" ? "blockquote" : "p", { "data-source-text": "", class: "source-evidence-text" }, revision.evidence));
  }

  function card(notice, dismissed = false) {
    const id = notice.event_id;
    const read = preferences.read.includes(id);
    const displayPeriod = period(notice);
    const actions = notice.synthetic ? [] : [
      !dismissed && !read ? el("button", {
        type: "button", class: "btn btn-small", "data-read-notice": id,
      }, "Mark as read") : null,
      el("button", { type: "button", class: "btn btn-small",
        [dismissed ? "data-restore-notice" : "data-dismiss-notice"]: id,
      }, dismissed ? "Restore update" : "Dismiss"),
    ];
    return el("article", { class: "card alert-card", "data-notice-id": notice.id, tabindex: "-1" },
      el("div", { class: "card-title" }, el("h4", {}, notice.title),
        pill(notice.synthetic ? "Simulation" : read ? "Read" : "Unread", notice.synthetic ? "pill-warn" : "pill-ok")),
      el("p", { class: "alert-route" }, labels[notice.status]),
      notice.reopening_unconfirmed
        ? el("p", { class: "hint" }, "Scheduled end passed; reopening unconfirmed.") : null,
      notice.previous_period ? el("p", { class: "alert-route" }, "Dates changed") : null,
      el("p", {}, notice.location),
      el("p", { class: "hint" }, notice.modes.length
        ? notice.modes.map((mode) => el("span", {}, labels[mode] || mode, " "))
        : "Travel modes unspecified"),
      displayPeriod ? el("p", {}, el("span", {}, "Planned period"), " ", displayPeriod,
        notice.hours ? " · " + notice.hours : null)
        : notice.status === "closure_announced" ? el("p", { class: "hint" }, "Closure dates unspecified") : null,
      el("p", { class: "hint" }, "Route impact unmodeled"),
      el("details", { class: "alert-details" }, el("summary", {}, "Source evidence"),
        el("p", {}, el("span", {}, "Source last checked"), " ", el("time", { datetime: notice.last_checked }, notice.last_checked)),
        el("p", {}, notice.source_url
          ? el("a", { href: notice.source_url, target: "_blank", rel: "noopener noreferrer" }, "Hamar municipality")
          : "Saved simulation fixture"),
        evidenceBlock(notice),
        notice.previous_period ? el("div", {},
          el("p", {}, el("span", {}, "Previous planned period"), " ", period(notice.previous_period) || "—"),
          el("p", {}, el("span", {}, "Source last checked"), " ", notice.previous_period.last_checked),
          evidenceBlock(notice.previous_period)) : null),
      actions.length ? el("div", { class: "notification-actions" }, actions) : null);
  }

  function render() {
    $("city-notifications").hidden = !preferences.hamar;
    $("journey-notifications").hidden = !preferences.journeys;
    $("refresh-notifications").disabled = loading || !(preferences.hamar || preferences.journeys);
    const real = notices.filter((notice) => !notice.synthetic);
    const visible = real.filter((notice) => !preferences.dismissed.includes(notice.event_id));
    const dismissed = real.filter((notice) => preferences.dismissed.includes(notice.event_id));
    $("city-notice-list").replaceChildren(...visible.map((notice) => card(notice)));
    $("dismissed-city-list").replaceChildren(...dismissed.map((notice) => card(notice, true)));
    $("dismissed-city-notices").hidden = !dismissed.length;
    $("simulation-notice-list").replaceChildren(...notices.filter((notice) => notice.synthetic).map((notice) => card(notice)));
    status.textContent = unavailable
      ? "Saved notices unavailable. Any displayed notices are from the previous load."
      : loading ? "Loading saved notices…"
        : ready && !visible.length ? "No visible Hamar-area notices." : "";
    const unread = visible.filter((notice) => !preferences.read.includes(notice.event_id)).length;
    $("notifications-count").textContent = preferences.hamar && unread ? `(${unread})` : "";
  }

  async function refreshCity() {
    if (!preferences.hamar || loading) return;
    loading = true;
    render();
    try {
      const result = await api("/api/notifications");
      notices = result.notices;
      ready = true;
      unavailable = false;
    } catch {
      unavailable = true;
    } finally {
      loading = false;
      render();
    }
  }

  function openCentre() {
    dialog.showModal();
    if (!ready) refreshCity();
  }

  button.addEventListener("click", openCentre);
  $("refresh-journey-alerts").addEventListener("click", openCentre);
  $("close-notifications").addEventListener("click", () => dialog.close());
  $("refresh-notifications").addEventListener("click", () => {
    refreshCity();
    if (preferences.journeys) refreshJourneyAlerts();
  });
  dialog.addEventListener("change", (event) => {
    if (event.target !== followHamar && event.target !== followJourneys) return;
    preferences.hamar = followHamar.checked;
    preferences.journeys = followJourneys.checked;
    save();
    render();
    if (!ready) refreshCity();
  });
  $("city-notifications").addEventListener("click", (event) => {
    const { readNotice, dismissNotice, restoreNotice } = event.target.dataset;
    if (!readNotice && !dismissNotice && !restoreNotice) return;
    const noticeId = event.target.closest("article").dataset.noticeId;
    if (readNotice) preferences.read.push(readNotice);
    if (dismissNotice) preferences.dismissed.push(dismissNotice);
    if (restoreNotice) preferences.dismissed = preferences.dismissed.filter((id) => id !== restoreNotice);
    save();
    render();
    const target = dismissNotice ? $("dismissed-city-notices").querySelector("summary")
      : $("city-notice-list").querySelector(`[data-notice-id="${noticeId}"]`);
    target?.focus();
  });
  render();
  refreshCity();
})();
