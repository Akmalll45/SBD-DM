(function () {
  window.refreshIcons = function () {
    if (window.lucide && typeof lucide.createIcons === "function") {
      lucide.createIcons({
        attrs: { "aria-hidden": "true", "stroke-width": 1.8 }
      });
    }
  };
  renderNavbar();
  renderFooter();
  if (typeof initHome === "function") initHome();
  if (typeof initShop === "function") initShop();
  if (typeof initProduct === "function") initProduct();
  if (typeof initAuth === "function") initAuth();
  refreshIcons();
})();
