document.addEventListener("DOMContentLoaded", () => {
  const search = document.getElementById("recordSearch");
  const table = document.getElementById("recordsTable");
  if (search && table) {
    search.addEventListener("input", () => {
      const query = search.value.toLowerCase().trim();
      table.querySelectorAll("tbody tr").forEach(row => {
        row.hidden = !row.innerText.toLowerCase().includes(query);
      });
    });
  }

  const today = new Date();
  const localDate = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  document.querySelectorAll('input[type="date"]').forEach(input => {
    if (!input.min) input.min = localDate;
  });

  document.querySelectorAll("form[onsubmit]").forEach(form => {
    form.addEventListener("submit", event => {
      if (form.dataset.confirmed === "yes") return;
    });
  });
});