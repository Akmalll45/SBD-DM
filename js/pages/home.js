window.initHome = function () {
  const categories = ["Running","Football","Basketball","Badminton","Fitness & Gym","Sportswear","Outdoor","Accessories"];
  const categoryImages = [
    "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1546519638-68e109498ffc?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1581009146145-b5ef050c2e1e?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=700&q=80",
    "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?auto=format&fit=crop&w=700&q=80"
  ];

  document.getElementById("category-grid").innerHTML = categories.map((category, index) => `
    <a class="category-card" href="shop.html?category=${encodeURIComponent(category)}">
      <img src="${categoryImages[index]}" alt="${category}" loading="lazy">
      <span>${category}</span>
    </a>`).join("");

  window.renderProducts = function(containerId, products) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = products.map(product => `
      <article class="product-card">
        <a class="product-card__image" href="product.html?id=${product.id}">
          ${product.isNew ? '<span class="product-card__label">NEW</span>' : ""}
          <img src="${product.images[0]}" alt="${product.name}" loading="lazy">
          <button class="icon-button product-card__wishlist wishlist-button" type="button" data-id="${product.id}" aria-label="Add ${product.name} to wishlist">
            <i data-lucide="heart"></i>
          </button>
        </a>
        <div class="product-card__body">
          <div class="product-card__brand">${product.brand}</div>
          <h3 class="product-card__name"><a href="product.html?id=${product.id}">${product.name}</a></h3>
          <div class="product-card__footer">
            <div><span class="price">${formatIDR(product.discountPrice || product.price)}</span>${product.discountPrice ? `<span class="price--old">${formatIDR(product.price)}</span>` : ""}</div>
            <button class="product-card__cart add-cart-button" type="button" data-id="${product.id}" aria-label="Add ${product.name} to cart"><i data-lucide="shopping-bag"></i></button>
          </div>
        </div>
      </article>`).join("");
  };

  renderProducts("featured-products", PRODUCTS.filter(p => p.isFeatured).slice(0, 4));
  renderProducts("new-products", PRODUCTS.filter(p => p.isNew).slice(0, 4));
  document.getElementById("brand-grid").innerHTML = ["Nike","Adidas","Puma","ASICS","Under Armour","New Balance"].map(brand =>
    `<a class="brand-item" href="shop.html?brand=${encodeURIComponent(brand)}">${brand}</a>`).join("");

  document.getElementById("newsletter-form").addEventListener("submit", event => {
    event.preventDefault();
    window.toast.show("You have subscribed successfully. Demo only.");
    event.currentTarget.reset();
  });
  document.querySelectorAll(".add-cart-button").forEach(button => button.addEventListener("click", () => {
    const cart = store.get("hs-cart", []);
    const id = Number(button.dataset.id);
    const existing = cart.find(item => item.id === id);
    if (existing) existing.quantity += 1; else cart.push({id, quantity: 1});
    store.set("hs-cart", cart);
    renderNavbar();
    toast.show("Product added to cart.");
  }));
  document.querySelectorAll(".wishlist-button").forEach(button => button.addEventListener("click", event => {
    event.preventDefault();
    const id = Number(button.dataset.id);
    const wishlist = store.get("hs-wishlist", []);
    if (!wishlist.includes(id)) wishlist.push(id);
    store.set("hs-wishlist", wishlist);
    renderNavbar();
    toast.show("Product added to wishlist.");
  }));
};
