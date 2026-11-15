import { icon } from "./icons.js";

export function showAboutDialog({ t, showDialog, closeDialog }) {
  const body = document.createElement("div");
  body.className = "about-content";

  const project = document.createElement("header");
  project.className = "about-project";
  const projectIcon = document.createElement("span");
  projectIcon.className = "about-project-icon";
  projectIcon.innerHTML = icon("music");
  const projectCopy = document.createElement("span");
  projectCopy.className = "about-project-copy";
  const projectName = document.createElement("strong");
  projectName.textContent = "astrbot_plugin_music";
  const projectSummary = document.createElement("span");
  projectSummary.textContent = t("aboutSummary");
  projectCopy.append(projectName, projectSummary);
  project.append(projectIcon, projectCopy);
  body.append(project);

  const attribution = document.createElement("p");
  attribution.className = "about-attribution";
  const nekoLink = document.createElement("a");
  nekoLink.href = "https://github.com/FantasyNetworkCN/NekoMusic";
  nekoLink.target = "_blank";
  nekoLink.rel = "noopener noreferrer";
  attribution.append(t("attributionPrefix"));
  nekoLink.textContent = t("apiName");
  attribution.append(nekoLink, t("attributionSuffix"));
  body.append(attribution);

  const appendSection = (title, items) => {
    const section = document.createElement("section");
    section.className = "about-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    const links = document.createElement("div");
    links.className = "about-link-list";
    for (const { label, detail, url } of items) {
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      const copy = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = label;
      copy.append(name);
      if (detail) {
        const description = document.createElement("small");
        description.textContent = detail;
        copy.append(description);
      }
      link.append(copy);
      link.insertAdjacentHTML("beforeend", icon("external"));
      links.append(link);
    }
    section.append(heading, links);
    body.append(section);
  };

  appendSection(t("projectSection"), [
    {
      label: t("pluginSource"),
      url: "https://github.com/Zhalslar/astrbot_plugin_music",
    },
    { label: t("maintainer"), url: "https://github.com/Zhalslar" },
    {
      label: t("license"),
      url: "https://www.gnu.org/licenses/agpl-3.0.html",
    },
  ]);
  appendSection(t("musicServicesSection"), [
    { label: t("neteaseMusic"), url: "https://music.163.com/" },
    { label: t("qqMusic"), url: "https://y.qq.com/" },
    { label: t("kugouMusic"), url: "https://www.kugou.com/" },
    { label: t("kuwoMusic"), url: "https://www.kuwo.cn/" },
    { label: t("sodaMusic"), url: "https://music.douyin.com/qishui/" },
    { label: t("appleMusic"), url: "https://music.apple.com/" },
    { label: t("nekoMusic"), url: "https://music.nekocore.cn/" },
  ]);
  appendSection(t("creditsSection"), [
    { label: t("astrbotProject"), url: "https://github.com/AstrBotDevs/AstrBot" },
    { label: t("nekoSource"), url: "https://github.com/FantasyNetworkCN/NekoMusic" },
    { label: t("apiDocs"), url: "https://github.com/FantasyNetworkCN/NekoMusicDocs" },
    {
      label: t("apiEnhanced"),
      url: "https://github.com/neteasecloudmusicapienhanced/api-enhanced",
    },
    { label: t("kugouApi"), url: "https://github.com/MakcRe/KuGouMusicApi" },
    {
      label: t("kuwoReference"),
      url: "https://github.com/006lp/nonebot-plugin-kuwo",
    },
    { label: t("txqqService"), url: "https://music.txqq.pro/" },
  ]);
  appendSection(t("contributorsSection"), [
    {
      label: "Zhalslar",
      detail: t("maintainerRole"),
      url: "https://github.com/Zhalslar",
    },
    {
      label: "LWELY",
      detail: t("qqCodeRole"),
      url: "https://github.com/LWELY",
    },
    {
      label: "006lp",
      detail: t("kuwoRole"),
      url: "https://github.com/006lp",
    },
  ]);

  const disclaimer = document.createElement("p");
  disclaimer.className = "about-disclaimer";
  disclaimer.textContent = t("disclaimer");
  body.append(disclaimer);
  showDialog(t("about"), body, [
    { label: t("dismiss"), action: closeDialog },
  ]);
}
