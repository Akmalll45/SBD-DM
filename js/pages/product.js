window.initProduct = function () {
  const id = Number(new URLSearchParams(location.search).get("id")) || PRODUCTS[0].id;
  const product = PRODUCTS.find(p => p.id === id) || PRODUCTS[0];
  document.title = `${product.name} | Hendra Sport`;
  const container = document.getElementById("product-detail");
  container.innerHTML = `
    <section class="product-detail-section">
      <div class="container product-detail-layout">
        <div class="product-gallery">
          <div class="product-main-image"><img id="main-product-image" src="${product.images[0]}" alt="${product.name}"></div>
        </div>
        <div class="product-info">
          <div class="product-card__brand">${product.brand} • ${product.category}</div>
          <h1>${product.name}</h1>
          <div class="product-rating">★ ${product.rating} <span>(${product.reviewCount} reviews)</span></div>
          <div class="product-detail-price"><span>${formatIDR(product.discountPrice || product.price)}</span>${product.discountPrice ? `<del>${formatIDR(product.price)}</del>` : ""}</div>
          <p class="product-description">${product.description}</p>
          <div class="option-field">
            <div class="option-heading"><strong>Size</strong><span id="size-status">Select a size</span></div>
            <div class="option-list">${product.sizes.map(size => `<button class="size-option" type="button" data-value="${size}">${size}</button>`).join("")}</div>
          </div>
          <div class="option-field">
            <div class="option-heading"><strong>Color</strong><span id="color-status">Select a color</span></div>
            <div class="option-list">${product.colors.map(color => `<button class="color-option" type="button" data-value="${color}">${color}</button>`).join("")}</div>
          </div>
          <div class="stock-line"><span></span> Demo stock: ${product.stock} available</div>
          <div class="product-actions">
            <div class="quantity-control"><button id="qty-minus" type="button" aria-label="Decrease quantity">−</button><output id="product-quantity">1</output><button id="qty-plus" type="button" aria-label="Increase quantity">+</button></div>
            <button class="button button--dark product-buy-button" id="add-detail-cart" type="button">Add to Cart</button>
            <button class="icon-button detail-wishlist" type="button" aria-label="Add to wishlist"><i data-lucide="heart"></i></button>
          </div>
          <button class="button button--outline buy-now" type="button">Buy Now</button>
        </div>
      </div>
    </section>`;
  let quantity = 1, size = "", color = "";
  container.querySelectorAll(".size-option").forEach(button => button.addEventListener("click", () => {
    container.querySelectorAll(".size-option").forEach(v => v.classList.remove("selected"));
    button.classList.add("selected"); size = button.dataset.value; document.getElementById("size-status").textContent = size;
  }));
  container.querySelectorAll(".color-option").forEach(button => button.addEventListener("click", () => {
    container.querySelectorAll(".color-option").forEach(v => v.classList.remove("selected"));
    button.classList.add("selected"); color = button.dataset.value; document.getElementById("color-status").textContent = color;
  }));
  document.getElementById("qty-minus").addEventListener("click", () => { quantity = Math.max(1, quantity - 1); document.getElementById("product-quantity").value = quantity; });
  document.getElementById("qty-plus").addEventListener("click", () => { quantity = Math.min(product.stock, quantity + 1); document.getElementById("product-quantity").value = quantity; });
  function addToCart(goToCart = false) {
    if (!size || !color) { toast.show("Please select a size and color.", "error"); return; }
    const cart = store.get("hs-cart", []);
    const key = `${product.id}-${size}-${color}`;
    const item = cart.find(v => v.key === key);
    item ? item.quantity += quantity : cart.push({ id: product.id, key, size, color, quantity });
    store.set("hs-cart", cart); renderNavbar(); toast.show("Product added to cart.");
    if (goToCart) location.href = "cart.html";
  }
  document.getElementById("add-detail-cart").addEventListener("click", () => addToCart(false));
  container.querySelector(".buy-now").addEventListener("click", () => addToCart(true));
  container.querySelector(".detail-wishlist").addEventListener("click", () => {
    const list = store.get("hs-wishlist", []);
    if (!list.includes(product.id)) list.push(product.id);
    store.set("hs-wishlist", list); renderNavbar(); toast.show("Product added to wishlist.");
  });
  const related = PRODUCTS.filter(p => p.category === product.category && p.id !== product.id).slice(0, 4);
  document.getElementById("related-products").innerHTML = related.length ? related.map(p => `
    <article class="product-card"><a class="product-card__image" href="product.html?id=${p.id}"><img src="${p.images[0]}" alt="${p.name}" loading="lazy"></a>
    <div class="product-card__body"><div class="product-card__brand">${p.brand}</div><h3 class="product-card__name"><a href="product.html?id=${p.id}">${p.name}</a></h3><span class="price">${formatIDR(p.discountPrice || p.price)}</span></div></article>`).join("") : "<p>No related products.</p>";
};
