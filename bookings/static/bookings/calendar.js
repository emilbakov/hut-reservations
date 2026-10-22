document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("availability-calendar");
  if (!root) return;

  const title = document.getElementById("cal-title");
  const prev = document.getElementById("cal-prev");
  const next = document.getElementById("cal-next");
  const arrival = document.querySelector('#find-stay input[name="check_in"]');
  const departure = document.querySelector('#find-stay input[name="check_out"]');
  const endpoint = root.dataset.endpoint;
  const hutSlug = root.dataset.hutSlug || "";

  const now = new Date();
  const firstMonth = new Date(now.getFullYear(), now.getMonth(), 1);
  let cursor = new Date(firstMonth);
  let requestNumber = 0;
  const weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  const iso = (y, m, d) => `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  const todayKey = iso(now.getFullYear(), now.getMonth(), now.getDate());
  const make = (tag, cls, value) => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (value !== undefined) el.textContent = value;
    return el;
  };

  async function render() {
    const thisRequest = ++requestNumber;
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    if (title) title.textContent = cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" });
    if (prev) prev.disabled = year === firstMonth.getFullYear() && month === firstMonth.getMonth();
    root.replaceChildren(make("p", "cal-loading", "Loading availability…"));

    const params = new URLSearchParams({ year: String(year), month: String(month + 1) });
    if (hutSlug) params.set("hut", hutSlug);
    try {
      if (!endpoint) throw new Error("Missing calendar endpoint");
      const response = await fetch(`${endpoint}${endpoint.includes("?") ? "&" : "?"}${params}`, { credentials: "same-origin" });
      if (!response.ok) throw new Error(`Calendar request failed (HTTP ${response.status})`);
      const data = await response.json();
      if (!Array.isArray(data.days)) throw new Error("Calendar response is missing days");
      if (thisRequest !== requestNumber) return;

      const byDate = new Map(data.days.map(day => [day.date, day]));
      root.replaceChildren();
      weekdays.forEach(day => root.append(make("span", "cal-weekday", day)));
      const offset = (new Date(year, month, 1).getDay() + 6) % 7;
      for (let i = 0; i < offset; i++) root.append(make("span", "cal-empty", ""));
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      for (let day = 1; day <= daysInMonth; day++) {
        const key = iso(year, month, day);
        const info = byDate.get(key);
        const free = Number(info?.free_beds || 0);
        const available = Boolean(info) && free > 0 && key >= todayKey;
        const button = make("button", `cal-day ${available ? "cal-free" : info ? "cal-full" : "cal-disabled"}`, String(day));
        button.type = "button";
        button.disabled = !available;
        button.title = info ? `${free} beds free` : "Not available";
        button.setAttribute("aria-label", info ? `${key}: ${free} beds free` : `${key}: not bookable`);
        if (arrival?.value === key) button.classList.add("cal-selected");
        if (available) button.addEventListener("click", () => {
          if (!arrival) return;
          arrival.value = key;
          arrival.dispatchEvent(new Event("change", { bubbles: true }));
          if (departure && (!departure.value || departure.value <= key)) {
            const following = new Date(year, month, day + 1);
            departure.value = iso(following.getFullYear(), following.getMonth(), following.getDate());
            departure.dispatchEvent(new Event("change", { bubbles: true }));
          }
          root.querySelectorAll(".cal-selected").forEach(el => el.classList.remove("cal-selected"));
          button.classList.add("cal-selected");
          arrival.focus();
        });
        root.append(button);
      }
    } catch (error) {
      if (thisRequest !== requestNumber) return;
      console.error("Availability calendar:", error);
      root.replaceChildren(make("p", "cal-error", "Availability couldn't be loaded. Please choose your dates above."));
    }
  }

  prev?.addEventListener("click", () => {
    const candidate = new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1);
    if (candidate >= firstMonth) { cursor = candidate; render(); }
  });
  next?.addEventListener("click", () => {
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
    render();
  });
  render();
});
