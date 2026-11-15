import { bridge } from "./api.js";

export function createLoginManager({ dialog, dialogBody, t, toast, showDialog }) {
  let pollTimer;

  const stop = () => {
    clearTimeout(pollTimer);
    pollTimer = undefined;
  };

  const refresh = async (request) => {
    if (!dialog.open || dialogBody.dataset.request !== request) return;
    try {
      render(await bridge.apiGet("logins", {}), request);
    } catch (error) {
      if (!dialog.open || dialogBody.dataset.request !== request) return;
      const failed = document.createElement("div");
      failed.className = "list-status error";
      failed.textContent = error?.message || t("loadError");
      dialogBody.replaceChildren(failed);
    }
  };

  const render = (result, request) => {
    if (!dialog.open || dialogBody.dataset.request !== request) return;
    const body = document.createElement("div");
    body.className = "login-content";
    const hint = document.createElement("p");
    hint.className = "login-hint";
    hint.textContent = t("loginHint");
    body.append(hint);

    const providers = Array.isArray(result?.platforms) ? result.platforms : [];
    const list = document.createElement("div");
    list.className = "login-provider-list";
    if (!providers.length) {
      const empty = document.createElement("div");
      empty.className = "list-status";
      empty.textContent = t("noLoginProviders");
      list.append(empty);
    }

    let hasActiveLogin = false;
    for (const provider of providers) {
      const active = ["starting", "waiting"].includes(provider.status);
      hasActiveLogin ||= active;
      const card = document.createElement("section");
      card.className = `login-provider${provider.qr_code ? " has-qr" : ""}`;
      const header = document.createElement("header");
      const name = document.createElement("strong");
      name.textContent = t(
        provider.name === "qqmusic" ? "qqmusicName" : "kugouName",
      );
      const badge = document.createElement("span");
      badge.className = `login-badge${provider.configured ? " configured" : ""}`;
      badge.textContent = t(provider.configured ? "loggedIn" : "notLoggedIn");
      header.append(name, badge);

      const main = document.createElement("div");
      main.className = "login-provider-main";
      if (provider.qr_code) {
        const qr = document.createElement("img");
        qr.className = "login-qr";
        qr.src = provider.qr_code;
        qr.alt = `${name.textContent} ${t("scanQr")}`;
        main.append(qr);
      }
      const controls = document.createElement("div");
      controls.className = "login-provider-controls";
      const status = document.createElement("p");
      const statusKey = {
        starting: "loginStarting",
        waiting: "loginWaiting",
        success: "loginSuccess",
        expired: "loginExpired",
        error: "loginFailed",
        busy: "loginBusy",
      }[provider.status];
      status.textContent = statusKey
        ? t(statusKey)
        : t(provider.configured ? "loggedIn" : "notLoggedIn");
      status.className = `login-status ${provider.status || "idle"}`;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "text-button login-action";
      button.disabled = active;
      button.textContent = active
        ? t("loginAwaiting")
        : t(provider.configured ? "relogin" : "login");
      button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = t("loginStarting");
        try {
          await bridge.apiPost(`logins/${encodeURIComponent(provider.name)}`, {});
          await refresh(request);
        } catch (error) {
          toast(error?.message || t("loginFailed"));
          await refresh(request);
        }
      });
      controls.append(status, button);
      main.append(controls);
      card.append(header, main);
      list.append(card);
    }
    body.append(list);
    dialogBody.replaceChildren(body);

    stop();
    if (hasActiveLogin) pollTimer = setTimeout(() => refresh(request), 2000);
  };

  const show = () => {
    const body = document.createElement("div");
    body.className = "login-content";
    const loading = document.createElement("div");
    loading.className = "list-status";
    loading.textContent = t("loading");
    body.append(loading);
    showDialog(t("loginManagement"), body, [
      { label: t("dismiss"), action: () => dialog.close() },
    ]);
    refresh(dialogBody.dataset.request);
  };

  return { show, stop };
}
