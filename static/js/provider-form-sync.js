document.addEventListener("DOMContentLoaded", () => {
  const provForm = document.getElementById("providerForm");
  if (!provForm) return; // falls das Element nicht existiert

  const provHidden = document.getElementById("providerHidden");
  const svcHidden  = document.getElementById("providerServiceHidden");

  provForm.addEventListener("click", (e) => {
    const t = e.target;
    if (t && t.tagName === "BUTTON" && t.name === "provider") {
      if (svcHidden)  svcHidden.value  = "";        // Service zurücksetzen
      if (provHidden) provHidden.value = t.value;   // Provider setzen
    }
  });
});
