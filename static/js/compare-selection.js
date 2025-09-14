const STORAGE_KEY = "selected_ids";

function getStoredSelection() {
  return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
}
function updateStoredSelection(selectedIds) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedIds));
}
function updateCompareForm(selectedIds) {
  const compareBtn = document.getElementById("compareBtn");
  const form = document.getElementById("compareForm");
  if (!compareBtn || !form) return;

  compareBtn.disabled = selectedIds.length !== 2;

  form.querySelectorAll('input[type="hidden"]').forEach(el => el.remove());
  selectedIds.forEach(id => {
    const hidden = document.createElement("input");
    hidden.type = "hidden";
    hidden.name = "ids";
    hidden.value = id;
    form.appendChild(hidden);
  });
}
function handleCheckbox(checkbox) {
  let selectedIds = getStoredSelection();

  if (checkbox.checked) {
    if (selectedIds.length >= 2) {
      checkbox.checked = false;
      alert("Bitte nur zwei Zeilen auswählen.");
      return;
    }
    selectedIds.push(checkbox.value);
  } else {
    selectedIds = selectedIds.filter(id => id !== checkbox.value);
  }

  updateStoredSelection(selectedIds);
  updateCompareForm(selectedIds);
}
function restoreCheckboxSelection() {
  const selectedIds = getStoredSelection();
  document.querySelectorAll('input[name="ids"]').forEach(cb => {
    if (selectedIds.includes(cb.value)) cb.checked = true;
  });
  updateCompareForm(selectedIds);
}
function clearSelection() {
  localStorage.removeItem(STORAGE_KEY);
  document.querySelectorAll('input[name="ids"]').forEach(cb => cb.checked = false);
  updateCompareForm([]);
}

// Für deine HTML-Attribute wie onclick="handleCheckbox(this)" / onclick="clearSelection()"
window.handleCheckbox = handleCheckbox;
window.clearSelection = clearSelection;

document.addEventListener("DOMContentLoaded", restoreCheckboxSelection);