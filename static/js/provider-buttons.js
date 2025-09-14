document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector('form[action="/"]') || document.querySelector("form");
  if (!form) return;

  let providerInput = form.querySelector('[name="provider"]');
  if (!providerInput) {
    providerInput = document.createElement("input");
    providerInput.type = "hidden";
    providerInput.name = "provider";
    form.appendChild(providerInput);
  }

  document.querySelectorAll(".provider-buttons .pill").forEach(btn => {
    btn.addEventListener("click", () => {
      const value = btn.dataset.provider || "";
      providerInput.value = value;

      document.querySelectorAll(".provider-buttons .pill")
        .forEach(b => b.setAttribute("aria-pressed", b === btn ? "true" : "false"));

      form.submit();
    });
  });

  const current = providerInput.value || "";
  document.querySelectorAll(".provider-buttons .pill").forEach(b => {
    b.setAttribute("aria-pressed", (b.dataset.provider || "") === current ? "true" : "false");
  });
});