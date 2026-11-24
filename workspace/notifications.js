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
  let cityRequest;
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
    notice_reviewed: "Reviewed official notice",
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
      notice.location ? el("p", {}, notice.location) : null,
      notice.summary ? el("p", {}, el("strong", {}, "Reviewer summary"), " ", el("span", { "data-source-text": "" }, notice.summary)) : null,
      notice.status === "notice_reviewed" ? el("p", { class: "hint" }, "Closure dates and current access are unverified.") : null,
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
    if (!preferences.hamar) return;
    if (loading) return cityRequest;
    loading = true;
    render();
    cityRequest = api("/api/notifications")
      .then((result) => {
        notices = result.notices;
        ready = true;
        unavailable = false;
      })
      .catch(() => { unavailable = true; })
      .finally(() => {
        loading = false;
        render();
      });
    return cityRequest;
  }

  function openCentre() {
    dialog.showModal();
    if (!ready) refreshCity();
    loadReviewQueue();
  }

  const checkButton = $("check-official-notices");
  const checkStatus = $("official-notice-status");
  const resultLabels = {
    new: "New notice", baseline: "First saved snapshot", changed: "Source text changed",
    unchanged: "Unchanged", unavailable: "Source unavailable",
    checked: "Index checked", no_links: "No approved notice links found",
    unlisted: "Previously known source absent from index",
  };
  let reviewBusy = false;

  function snapshotBlock(label, snapshot) {
    return el("details", { open: label === "Retrieved source text" },
      el("summary", {}, label),
      el("p", {}, el("time", { datetime: snapshot.retrieved_at }, snapshot.retrieved_at)),
      el("p", { class: "hint" }, "SHA-256 ", el("code", {}, snapshot.text_sha256)),
      el("pre", { class: "official-source-text", tabindex: "0" }, snapshot.text));
  }

  function reviewCard(item) {
    const source = item.snapshot;
    const quote = el("textarea", { required: true, minlength: "12", maxlength: "500", rows: "2" });
    const summary = el("textarea", { maxlength: "400", rows: "2" });
    const accept = el("button", { type: "submit", class: "btn btn-small" }, "Accept reviewed evidence");
    const form = el("form", { class: "official-review-form" },
      el("label", {}, "Exact quotation from the retrieved text", quote),
      el("label", {}, "Reviewer summary (optional)", summary),
      el("p", { class: "hint" }, "Acceptance replaces cards for this source. Closure dates and current access stay unverified."),
      accept);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const exact = quote.value.trim();
      if (exact.length < 12 || !source.text.includes(exact)) {
        checkStatus.textContent = "Enter an exact quotation of at least 12 characters.";
        quote.focus();
        return;
      }
      accept.disabled = true;
      await runReviewAction("/api/official-notices/accept", {
        url: source.url, text_sha256: source.text_sha256, quote: exact, summary: summary.value,
      }, "Reviewed evidence accepted.");
      accept.disabled = false;
    });
    return el("article", { class: "card", "data-review-url": source.url },
      el("h4", { "data-source-text": "" }, source.title),
      el("p", {}, resultLabels[item.status]),
      el("a", { href: source.url, target: "_blank", rel: "noopener noreferrer" }, "Open official notice"),
      snapshotBlock("Retrieved source text", source),
      item.previous ? snapshotBlock("Previous source text", item.previous) : null,
      form);
  }

  function renderReviewQueue(data) {
    const queue = $("official-notice-queue");
    const existing = new Map(Array.from(queue.children, (card) => [card.dataset.reviewUrl, card]));
    const cards = data.pending.map((item) => {
      const prior = existing.get(item.snapshot.url);
      if (prior && prior.dataset.revision === item.snapshot.text_sha256) return prior;
      const card = reviewCard(item);
      card.dataset.revision = item.snapshot.text_sha256;
      return card;
    });
    queue.replaceChildren(...(cards.length ? cards : [el("p", { class: "hint" }, "No changes pending review.")]));
    const check = data.last_check;
    $("official-check-details").hidden = !check;
    if (check) {
      $("official-check-results").replaceChildren(el("div", {},
        el("p", {}, el("time", { datetime: check.checked_at }, check.checked_at)),
        check.limited ? el("p", { class: "hint" }, "The article limit was reached.") : null,
        el("ul", {}, check.results.map((result) => el("li", {},
          el("a", { href: result.url, target: "_blank", rel: "noopener noreferrer" }, result.url),
          " · ", el("span", {}, resultLabels[result.status]))))));
    }
  }

  async function loadReviewQueue() {
    if (reviewBusy) return;
    reviewBusy = true;
    checkButton.disabled = true;
    try {
      renderReviewQueue(await api("/api/official-notices"));
    } catch {
      checkStatus.textContent = "Saved source reviews are unavailable.";
    } finally {
      reviewBusy = false;
      checkButton.disabled = false;
    }
  }

  async function runReviewAction(path, payload, message) {
    if (reviewBusy) return;
    reviewBusy = true;
    checkButton.disabled = true;
    checkStatus.textContent = payload.url ? "Saving review…" : "Checking official sources…";
    try {
      const data = await api(path, payload);
      renderReviewQueue(data);
      if (payload.url) {
        if (loading) await cityRequest;
        await refreshCity();
        checkStatus.focus();
      }
      checkStatus.textContent = !payload.url && data.last_check.results.some((item) => item.status === "unavailable")
        ? "Some official sources were unavailable. Reviewed notices were kept." : message;
    } catch {
      checkStatus.textContent = "The source action could not be completed. Reload the review queue and try again.";
    } finally {
      reviewBusy = false;
      checkButton.disabled = false;
    }
  }

  checkButton.addEventListener("click", () => {
    runReviewAction("/api/official-notices/check", {}, "Official source check finished.");
  });

  button.addEventListener("click", openCentre);
  $("refresh-journey-alerts").addEventListener("click", openCentre);
  $("close-notifications").addEventListener("click", () => dialog.close());
  $("refresh-notifications").addEventListener("click", () => {
    refreshCity();
    loadReviewQueue();
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
