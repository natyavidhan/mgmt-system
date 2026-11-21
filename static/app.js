/*
  The few things that need JavaScript.
  Everything else is plain HTML forms handled by Flask.
*/


// --- Inventory page: live search and the "Low stock only" switch -------------

const searchBox = document.querySelector("#search");
const lowStockSwitch = document.querySelector("#low-stock-only");
const itemRows = document.querySelectorAll("tr[data-status]");
const noMatchesMessage = document.querySelector("#no-matches");

function filterItems() {
  const query = searchBox.value.trim().toLowerCase();
  let shown = 0;

  for (const row of itemRows) {
    const matchesSearch = row.dataset.search.includes(query);
    const matchesSwitch = !lowStockSwitch.checked || row.dataset.status !== "ok";
    row.hidden = !(matchesSearch && matchesSwitch);
    if (!row.hidden) shown++;
  }

  noMatchesMessage.hidden = shown > 0;
}

if (searchBox) {
  searchBox.addEventListener("input", filterItems);
  lowStockSwitch.addEventListener("change", filterItems);
}


// --- Inventory page: the − and + buttons -------------------------------------
// Each click saves the change on the server, then updates the row and the
// totals in place, so the page doesn't have to reload.

async function changeStock(button) {
  const row = button.closest("tr");
  const form = new FormData();
  form.append("amount", button.dataset.amount);

  let response;
  try {
    response = await fetch(row.dataset.stockUrl, { method: "POST", body: form });
  } catch {
    alert("Couldn't reach the server. Is it still running?");
    return;
  }

  // Something's off (e.g. the login expired, so we got sent to the login
  // page). Reloading shows whatever the server wants us to see.
  if (!response.ok || response.redirected) {
    location.reload();
    return;
  }

  const result = await response.json();

  row.dataset.status = result.status;
  row.querySelector(".qty").textContent = result.quantity;
  row.querySelector('[data-amount="-1"]').disabled = result.quantity === 0;

  const badge = row.querySelector(".badge");
  badge.className = `badge ${result.status}`;
  badge.textContent = result.status_label;

  for (const [name, value] of Object.entries(result.stats)) {
    document.querySelector(`[data-stat="${name}"]`).textContent = value;
  }
}

for (const button of document.querySelectorAll(".stepper button")) {
  button.addEventListener("click", () => changeStock(button));
}


// --- Edit page: double-check before deleting ---------------------------------

for (const form of document.querySelectorAll("form[data-confirm]")) {
  form.addEventListener("submit", (event) => {
    if (!confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
}


// --- Every page: fade out the "Saved!" toasts after a few seconds ------------

for (const toast of document.querySelectorAll(".toast")) {
  setTimeout(() => toast.classList.add("hide"), 3500);
}
