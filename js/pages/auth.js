window.initAuth = function () {
  const back = document.getElementById("auth-back");
  back && back.addEventListener("click", () => history.length > 1 ? history.back() : location.assign("index.html"));

  const register = document.getElementById("register-form");
  if (register) {
    document.getElementById("toggle-password").addEventListener("click", function () {
      const password = document.getElementById("register-password");
      password.type = password.type === "password" ? "text" : "password";
    });
    register.addEventListener("submit", event => {
      event.preventDefault();
      const name = document.getElementById("register-name").value.trim();
      const email = document.getElementById("register-email").value.trim();
      const password = document.getElementById("register-password").value;
      const confirm = document.getElementById("register-confirm").value;
      document.querySelectorAll(".auth-error").forEach(node => node.textContent = "");
      if (name.length < 3) return document.getElementById("name-error").textContent = "Enter at least 3 characters.";
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return document.getElementById("email-error").textContent = "Enter a valid email address.";
      if (password.length < 6) return document.getElementById("password-error").textContent = "Use at least 6 characters.";
      if (password !== confirm) return document.getElementById("confirm-error").textContent = "Passwords do not match.";
      store.set("hs-profile", { name, email });
      store.set("hs-session", { name, email });
      toast.show("Demo account created successfully.");
      setTimeout(() => location.assign("index.html"), 800);
    });
  }

  const login = document.getElementById("login-form");
  if (login) {
    login.addEventListener("submit", event => {
      event.preventDefault();
      const email = document.getElementById("login-email").value.trim();
      const password = document.getElementById("login-password").value;
      if (!email || !password) {
        toast.show("Please enter your email and password.", "error");
        return;
      }
      store.set("hs-session", { email, name: "Hendra Sport User" });
      toast.show("Demo login successful.");
      setTimeout(() => location.assign("index.html"), 800);
    });
    document.getElementById("toggle-login-password").addEventListener("click", function () {
      document.getElementById("login-password").type = document.getElementById("login-password").type === "password" ? "text" : "password";
    });
  }
};
