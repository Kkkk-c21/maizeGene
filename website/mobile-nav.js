/* MaizeGene mobile navigation */
(function () {
  const toggleButtons = document.querySelectorAll("[data-menu-toggle]");

  toggleButtons.forEach(function (button) {
    const menuId = button.getAttribute("aria-controls");
    const menu = document.getElementById(menuId);

    if (!menu) return;

    function setMenuOpen(isOpen) {
      menu.classList.toggle("is-open", isOpen);
      button.setAttribute("aria-expanded", String(isOpen));
      button.setAttribute(
        "aria-label",
        isOpen ? "Close navigation menu" : "Open navigation menu"
      );
      const icon = button.querySelector("span");
      if (icon) icon.textContent = isOpen ? "×" : "☰";
    }

    button.addEventListener("click", function () {
      const isOpen = button.getAttribute("aria-expanded") === "true";
      setMenuOpen(!isOpen);
    });

    menu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        setMenuOpen(false);
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    });

    // Ensure the desktop layout is not left in an expanded mobile state.
    window.addEventListener("resize", function () {
      if (window.innerWidth > 600) {
        setMenuOpen(false);
      }
    });
  });
})();
