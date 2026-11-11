window.renderNavbar = function () {
  const header = document.getElementById("site-header");
  if (!header) return;
  const cart = window.store.get("hs-cart", []);
  const wishlist = window.store.get("hs-wishlist", []);
  const loggedIn = window.store.get("hs-session", null);
  const accountText = loggedIn ? "Account" : "Login";
  header.innerHTML = `
    <div class="site-header">
      <nav class="container navbar" aria-label="Main navigation">
        <a class="brand-logo-slot" href="index.html" aria-label="Hendra Sport homepage"><img src="assets/images/logo/hendra-sport-logo.jpg" alt="Hendra Sport"></a>
        <div class="nav-menu" id="nav-menu">
          <a href="index.html">Home</a>
          <a href="shop.html">Shop</a>
          <div class="dropdown" id="category-dropdown">
            <button class="nav-dropdown-toggle" type="button" aria-expanded="false">Categories <i data-lucide="chevron-down"></i></button>
            <div class="dropdown__menu">
              ${["Running","Football","Basketball","Badminton","Fitness & Gym","Sportswear","Outdoor","Accessories"].map(category =>
                `<a href="shop.html?category=${encodeURIComponent(category)}">${category}</a>`).join("")}
            </div>
          </div>
        </div>
        <div class="nav-actions">
          <button class="icon-button" id="search-toggle" type="button" aria-label="Search"><i data-lucide="search"></i></button>
          <a class="icon-button" href="wishlist.html" aria-label="Wishlist"><i data-lucide="heart"></i><span class="badge">${wishlist.length}</span></a>
          <a class="icon-button" href="cart.html" aria-label="Shopping cart"><i data-lucide="shopping-bag"></i><span class="badge">${cart.length}</span></a>
          <button class="icon-button menu-toggle" id="menu-toggle" type="button" aria-label="Open menu"><i data-lucide="menu"></i></button>
        </div>
        ${loggedIn ? `<a class="nav-account" href="profile.html">${accountText}</a>` : `<div class="nav-auth"><a class="nav-auth__login" href="login.html">Login</a><a class="nav-auth__register" href="register.html">Register</a></div>`}
      </nav>
    </div>
    <div class="search-panel" id="search-panel">
      <form class="container search-panel__inner" id="search-form">
        <label class="sr-only" for="global-search">Search products</label>
        <input id="global-search" type="search" placeholder="Search name, brand, or category">
        <button class="button button--dark" type="submit">Search</button>
      </form>
    </div>`;

  const menu = header.querySelector("#nav-menu");
  header.querySelector("#menu-toggle").addEventListener("click", () => {
    menu.classList.toggle("open");
    document.body.classList.toggle("menu-open", menu.classList.contains("open"));
  });
  const dropdown = header.querySelector("#category-dropdown");
  dropdown.querySelector("button").addEventListener("click", () => dropdown.classList.toggle("open"));
  const searchPanel = header.querySelector("#search-panel");
  header.querySelector("#search-toggle").addEventListener("click", () => searchPanel.classList.toggle("open"));
  header.querySelector("#search-form").addEventListener("submit", event => {
    event.preventDefault();
    const value = header.querySelector("#global-search").value.trim();
    window.location.href = `shop.html${value ? `?search=${encodeURIComponent(value)}` : ""}`;
  });
  if (window.refreshIcons) refreshIcons();
};
