window.renderFooter = function () {
  const footer = document.getElementById("site-footer");
  if (!footer) return;
  footer.className = "site-footer";
  footer.innerHTML = `
    <div class="container">
      <div class="footer-grid">
        <div class="footer-brand-column">
          <div class="footer-brand" aria-label="Hendra Sport"><img src="assets/images/logo/hendra-sport-logo.jpg" alt="Hendra Sport"></div>
          <p>A curated destination for performance gear and everyday sports essentials.</p>
          <p class="footer-slogan">MOVE FASTER. PLAY STRONGER.</p>
        </div>
        <div><h3>Quick Links</h3><ul><li><a href="index.html">Home</a></li><li><a href="shop.html">Shop</a></li><li><a href="shop.html?filter=new">New Arrivals</a></li><li><a href="shop.html">Categories</a></li></ul></div>
        <div><h3>Customer Service</h3><ul><li><a href="contact.html">Contact Us</a></li><li><a href="contact.html">FAQ</a></li><li>Shipping Information</li><li>Return & Refund Policy</li><li>Order Tracking</li></ul></div>
        <div><h3>About Hendra Sport</h3><ul><li><a href="about.html">About Us</a></li><li><a href="about.html">Our Story</a></li><li>Privacy Policy</li><li>Terms & Conditions</li></ul></div>
        <div><h3>Connect With Us</h3><ul><li>Instagram</li><li>Facebook</li><li>TikTok</li><li><a href="mailto:placeholder@example.com">Email</a></li></ul></div>
      </div>
      <div class="footer-bottom">© ${new Date().getFullYear()} Hendra Sport. Frontend demo.</div>
    </div>`;
};
