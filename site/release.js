(() => {
  const fallback = {
    version: "latest",
    release_url: "https://github.com/Kacoze/avream/releases/latest",
    assets: {
      monolith: "",
      daemon: "",
      ui: "",
      helper: "",
      meta: "",
      deb_split_archive: "",
    },
  };

  const manifestPathMeta = document.querySelector('meta[name="avream-manifest-path"]');
  const manifestPath = manifestPathMeta?.content || (location.pathname.includes("/docs/") ? "../release-manifest.json" : "./release-manifest.json");

  const basename = (url, defaultName = "") => {
    if (typeof url !== "string" || !url) return defaultName;
    try {
      const path = new URL(url).pathname;
      const parts = path.split("/").filter(Boolean);
      return parts.length ? parts[parts.length - 1] : defaultName;
    } catch {
      const parts = url.split("/").filter(Boolean);
      return parts.length ? parts[parts.length - 1] : defaultName;
    }
  };

  const setText = (selector, text) => {
    document.querySelectorAll(selector).forEach((el) => {
      el.textContent = text;
    });
  };

  const setHref = (selector, href) => {
    document.querySelectorAll(selector).forEach((el) => {
      if (el instanceof HTMLAnchorElement) {
        el.href = href;
      }
    });
  };

  const setCode = (selector, text) => {
    document.querySelectorAll(selector).forEach((el) => {
      el.textContent = text;
    });
  };

  const applyManifest = (manifest) => {
    const version = manifest.version || fallback.version;
    const releaseUrl = manifest.release_url || fallback.release_url;
    const assets = manifest.assets || {};
    const monolithName = basename(assets.monolith, `avream_${version}_amd64.deb`);
    const daemonName = basename(assets.daemon, `avream-daemon_${version}_amd64.deb`);
    const uiName = basename(assets.ui, `avream-ui_${version}_amd64.deb`);
    const helperName = basename(assets.helper, `avream-helper_${version}_amd64.deb`);
    const splitArchiveName = basename(assets.deb_split_archive, `avream-deb-split_${version}_amd64.tar.gz`);

    setText("[data-release-version]", version);
    setText("[data-release-monolith-name]", monolithName);
    setText("[data-release-daemon-name]", daemonName);
    setText("[data-release-ui-name]", uiName);
    setText("[data-release-helper-name]", helperName);
    setText("[data-release-split-archive-name]", splitArchiveName);
    setHref("[data-release-url]", releaseUrl);
    setHref("[data-release-split-archive-url]", assets.deb_split_archive || releaseUrl);

    setCode("[data-install-monolith-command]", `sudo apt install ./${monolithName}`);
    setCode(
      "[data-install-split-command]",
      `sudo apt install ./${daemonName} \\\n+  ./${uiName} \\\n+  ./${helperName}`
    );
    setCode("[data-reinstall-monolith-command]", `sudo apt install --reinstall ./${monolithName}`);

    const downloadBtn = document.querySelector("[data-release-download-btn]");
    if (downloadBtn) {
      downloadBtn.textContent = `Download v${version}`;
      if (downloadBtn instanceof HTMLAnchorElement) {
        downloadBtn.href = assets.monolith || releaseUrl;
      }
    }

    const footerVersion = document.querySelector("[data-footer-version]");
    if (footerVersion) {
      footerVersion.textContent = `AVream ${version} - Android webcam and microphone bridge for Linux.`;
    }
  };

  fetch(manifestPath, { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error("manifest fetch failed"))))
    .then((manifest) => applyManifest(manifest || fallback))
    .catch(() => applyManifest(fallback));
})();
