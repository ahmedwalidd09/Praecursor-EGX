(() => {
  const get = (id) => document.getElementById("news-" + id);
  const search = get("search"), category = get("category"), source = get("source");
  const list = get("items"), more = get("more"), refresh = get("refresh");
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Africa/Cairo", dateStyle: "medium", timeStyle: "short",
  });
  const PAGE_SIZE = 24;
  let data = null;
  let limit = PAGE_SIZE;

  function element(tag, content, className) {
    const node = document.createElement(tag);
    if (content) node.textContent = content;
    if (className) node.className = className;
    return node;
  }

  function safeLink(item) {
    try {
      const url = new URL(item.url);
      const host = item.source === "egx" ? "beta.egx.com.eg" : "www.arabfinance.com";
      if (url.protocol === "https:" && url.host === host && !url.username && !url.password) return url.href;
    } catch {}
    return null;
  }

  function renderItems() {
    if (!data) return;
    const needle = search.value.trim().toLowerCase();
    const matches = data.items.filter((item) => {
      const terms = [item.title, item.title_ar, item.category, ...item.symbols].join(" ").toLowerCase();
      return terms.includes(needle) && (!source.value || item.source === source.value)
        && (!category.value || item.category === category.value);
    });
    const append = document.createDocumentFragment();
    for (const item of matches.slice(0, limit)) {
      const row = element("li", null, "news-row");
      const date = item.published_at || item.source_updated_at;
      const time = element(date ? "time" : "span", date ? formatter.format(new Date(date)) : "Date unavailable", "news-time");
      if (date) time.dateTime = date;
      if (!item.published_at && item.source_updated_at) time.append(" · source update");
      const content = element("div");
      const publisher = data.sources[item.source]?.label || item.source;
      content.append(element("div", publisher, "news-publisher"));
      const heading = element("h3");
      const href = safeLink(item);
      const title = element(href ? "a" : "span", item.title);
      title.dir = "auto";
      if (href) {
        title.href = href;
        title.target = "_blank";
        title.rel = "noopener noreferrer";
      }
      heading.append(title);
      content.append(heading);
      if (item.title_ar && item.title_ar !== item.title) {
        const arabic = element("p", item.title_ar, "news-translation");
        arabic.lang = "ar";
        arabic.dir = "rtl";
        content.append(arabic);
      }
      const tags = element("ul", null, "news-tags");
      for (const tag of [item.category, ...item.symbols]) tags.append(element("li", tag));
      content.append(tags);
      row.append(time, content);
      append.append(row);
    }
    list.replaceChildren(append);
    get("count").textContent = matches.length
      ? "Showing " + Math.min(limit, matches.length) + " of " + matches.length
      : data.status === "unavailable" ? "" : "No items match these filters.";
    more.classList.toggle("hidden", matches.length <= limit);
  }

  function options(select, entries) {
    const selection = select.value;
    select.replaceChildren(select.options[0], ...entries.map(([value, label]) => new Option(label, value)));
    if (entries.some(([value]) => value === selection)) select.value = selection;
  }

  function render() {
    const status = get("status");
    const stamp = data.generated_at && formatter.format(new Date(data.generated_at));
    const failed = Object.values(data.sources).some((feed) => feed.status === "unavailable");
    status.classList.toggle("good", data.status === "ok" && !failed);
    if (data.status === "unavailable") status.textContent = "News is temporarily unavailable. Try refreshing in a minute.";
    else if (data.status === "stale") status.textContent = "Stale index · last cloud refresh " + stamp;
    else if (data.status === "cached") status.textContent = "Showing a saved index · last cloud refresh " + stamp;
    else status.textContent = "Cloud index refreshed " + stamp + (failed ? " · some sources unavailable" : "");

    const feeds = Object.entries(data.sources);
    const categories = [...new Set(data.items.map((item) => item.category))].sort();
    options(category, categories.map((value) => [value, value]));
    options(source, feeds.map(([id, feed]) => [id, feed.label]));
    get("feeds").replaceChildren(...feeds.map(([, feed]) => {
      const row = element("li");
      const observed = feed.last_success_at
        ? formatter.format(new Date(feed.last_success_at)) : "No successful check";
      const status = feed.status === "ok" ? "Last successful check" : "Unavailable · last successful check";
      row.append(element("strong", feed.label), element("span", feed.last_success_at ? status + " " + observed : observed));
      return row;
    }));
    renderItems();
  }

  async function load() {
    refresh.disabled = true;
    refresh.setAttribute("aria-busy", "true");
    try {
      const response = await fetch("/api/news", {cache: "no-store", signal: AbortSignal.timeout(40000)});
      if (!response.ok) throw new Error("News request failed");
      data = await response.json();
      render();
    } catch {
      get("status").textContent = data ? "Refresh failed. Showing the previous view." : "News is temporarily unavailable.";
      get("status").classList.remove("good");
    } finally {
      refresh.disabled = false;
      refresh.removeAttribute("aria-busy");
    }
  }

  for (const control of [search, category, source]) {
    control.addEventListener(control === search ? "input" : "change", () => {
      limit = PAGE_SIZE;
      renderItems();
    });
  }
  more.addEventListener("click", () => {
    const priorLimit = limit;
    limit += PAGE_SIZE;
    renderItems();
    list.children[priorLimit]?.querySelector("a")?.focus();
  });
  refresh.addEventListener("click", load);
  load();
})();
