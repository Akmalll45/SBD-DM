window.toast = {
  show(message, type = "success") {
    const root = document.getElementById("toast-root");
    if (!root) return;
    const node = document.createElement("div");
    node.className = "toast";
    node.innerHTML = `<i data-lucide="${type === "error" ? "circle-alert" : "circle-check"}"></i><span></span>`;
    node.querySelector("span").textContent = message;
    root.appendChild(node);
    if (window.refreshIcons) refreshIcons();
    setTimeout(() => node.remove(), 3200);
  }
};
