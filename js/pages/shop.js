window.initShop = function () {
  const params = new URLSearchParams(location.search);
  const categories = [...new Set(PRODUCTS.map(p => p.category))];
  const brands = [...new Set(PRODUCTS.map(p => p.brand))];
  document.getElementById("category-filter").insertAdjacentHTML("beforeend", categories.map(v => `<option>${v}</option>`).join(""));
  document.getElementById("brand-filter").insertAdjacentHTML("beforeend", brands.map(v => `<option>${v}</option>`).join(""));

  const search = document.getElementById("shop-search");
  const category = document.getElementById("category-filter");
  const brand = document.getElementById("brand-filter");
  const price = document.getElementById("price-filter");
  const newest = document.getElementById("new-filter");
  const sort = document.getElementById("sort-select");
  let visibleCount = 8;
  if (params.get("search")) search.value = params.get("search");
  if (params.get("category")) category.value = params.get("category");
  if (params.get("brand")) brand.value = params.get("brand");
  if (params.get("filter") === "new") newest.checked = true;

  function effectivePrice(p) { return p.discountPrice || p.price; }
  function render() {
    let list = PRODUCTS.filter(p => {
      const query = search.value.trim().toLowerCase();
      return (!query || [p.name, p.brand, p.category].some(v => v.toLowerCase().includes(query)))
        && (!category.value || p.category === category.value)
        && (!brand.value || p.brand === brand.value)
        && effectivePrice(p) <= Number(price.value)
        && (!newest.checked || p.isNew);
    });
    if (sort.value === "price-low") list.sort((a, b) => effectivePrice(a) - effectivePrice(b));
    if (sort.value === "price-high") list.sort((a, b) => effectivePrice(b) - effectivePrice(a));
    if (sort.value === "newest") list.sort((a, b) => Number(b.isNew) - Number(a.isNew));
    if (sort.value === "popular") list.sort((a, b) => b.reviewCount - a.reviewCount);

    document.getElementById("product-count").textContent = list.length;
    renderCatalogProducts(list.slice(0, visibleCount));
    document.getElementById("shop-empty").hidden = list.length !== 0;
    document.getElementById("load-more").hidden = visibleCount >= list.length;
  }
  function renderCatalogProducts(list) {
    document.getElementById("shop-products").innerHTML = list.map(p => `
      <article class="product-card catalog-card">
        <div class="catalog-card__media">
          <a class="product-card__image" href="product.html?id=${p.id}">
            ${p.isNew ? '<span class="product-card__label">NEW</span>' : ""}
            <img src="${p.images[0]}" alt="${p.name}" loading="lazy">
          </a>
          <button class="icon-button product-card__wishlist shop-wishlist" type="button" data-id="${p.id}" aria-label="Add ${p.name} to wishlist"><i data-lucide="heart"></i></button>
          <button class="catalog-card__quick-add shop-cart" type="button" data-id="${p.id}" aria-label="Add ${p.name} to cart"><i data-lucide="shopping-bag"></i><span>Quick add</span></button>
        </div>
        <div class="product-card__body">
          <div class="product-card__brand">${p.brand}</div>
          <h3 class="product-card__name"><a href="product.html?id=${p.id}">${p.name}</a></h3>
          <div class="product-card__footer"><div><span class="price">${formatIDR(effectivePrice(p))}</span>${p.discountPrice ? `<span class="price--old">${formatIDR(p.price)}</span>` : ""}</div>
          </div>
        </div>
      </article>`).join("");
    bindActions();
    if (window.refreshIcons) refreshIcons();
  }
  function bindActions() {
    document.querySelectorAll(".shop-cart").forEach(button => button.addEventListener("click", () => {
      const id = Number(button.dataset.id);
      const cart = store.get("hs-cart", []);
      const item = cart.find(v => v.id === id);
      item ? item.quantity++ : cart.push({ id, quantity: 1 });
      store.set("hs-cart", cart); renderNavbar(); toast.show("Product added to cart.");
    }));
    document.querySelectorAll(".shop-wishlist").forEach(button => button.addEventListener("click", () => {
      const id = Number(button.dataset.id);
      const list = store.get("hs-wishlist", []);
      if (!list.includes(id)) list.push(id);
      store.set("hs-wishlist", list); renderNavbar(); toast.show("Product added to wishlist.");
    }));
  }
  [search, category, brand, price, newest, sort].forEach(control => control.addEventListener("input", () => {
    visibleCount = 8;
    if (control === price) document.getElementById("price-output").value = formatIDR(Number(price.value));
    render();
  }));
  document.getElementById("clear-filter").addEventListener("click", () => {
    search.value = ""; category.value = ""; brand.value = ""; price.value = "3000000";
    newest.checked = false; sort.value = "featured";
    document.getElementById("price-output").value = formatIDR(3000000);
    render();
  });
  document.getElementById("load-more").addEventListener("click", () => { visibleCount += 4; render(); });
  render();
};
