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

  // Responsive authenticated workspace navigation.
  const navToggle = document.querySelector("[data-mobile-nav]");
  const sidebar = document.getElementById("main-sidebar");
  const scrim = document.querySelector("[data-sidebar-scrim]");
  const setSidebarOpen = (open) => {
    document.body.classList.toggle("sidebar-open", open);
    if (navToggle) navToggle.setAttribute("aria-expanded", open ? "true" : "false");
  };
  if (navToggle && sidebar) {
    navToggle.addEventListener("click", () => {
      setSidebarOpen(!document.body.classList.contains("sidebar-open"));
    });
    scrim?.addEventListener("click", () => setSidebarOpen(false));
    sidebar.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => setSidebarOpen(false));
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") setSidebarOpen(false);
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) setSidebarOpen(false);
    });
  }

  // Keep the doctor roster department list aligned to the selected branch.
  const rosterForm = document.querySelector(".doctor-create-form");
  if (rosterForm) {
    const branchSelect = rosterForm.querySelector("#doctor-branch");
    const branchHidden = rosterForm.querySelector('input[name="branch_id"]');
    const departmentSelect = rosterForm.querySelector("#doctor-department");
    const filterDepartments = () => {
      if (!departmentSelect) return;
      const branchId = branchSelect?.value || branchHidden?.value || "";
      let firstVisible = "";
      Array.from(departmentSelect.options).forEach(option => {
        if (!option.value) {
          option.hidden = false;
          return;
        }
        const visible = !!branchId && option.dataset.branch === branchId;
        option.hidden = !visible;
        if (visible && !firstVisible) firstVisible = option.value;
      });
      const selected = departmentSelect.selectedOptions[0];
      if (!selected || selected.hidden) departmentSelect.value = "";
      const placeholder = departmentSelect.options[0];
      if (placeholder) placeholder.textContent = branchId ? "Choose a department" : "Choose branch first";
    };
    branchSelect?.addEventListener("change", filterDepartments);
    filterDepartments();
  }

  // Live OPD slot availability. MySQL still validates the final booking
  // transaction and uniqueness constraint, so this is a usability layer.
  const appointmentForm = document.getElementById("appointment-booking-form");
  if (appointmentForm) {
    const doctorSelect = appointmentForm.querySelector("#appt-doctor");
    const dateInput = appointmentForm.querySelector("#appt-date");
    const slotSelect = appointmentForm.querySelector("#appt-time");
    const feedback = appointmentForm.querySelector("#slot-feedback");
    const submit = appointmentForm.querySelector("#appointment-submit");
    const availabilityUrl = appointmentForm.dataset.availabilityUrl;
    const originalSlotOptions = Array.from(slotSelect.options).slice(1).map(option => ({
      value: option.value,
      label: option.textContent
    }));
    let requestSequence = 0;

    const resetSlots = (message) => {
      slotSelect.innerHTML = "";
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = message;
      slotSelect.appendChild(placeholder);
      originalSlotOptions.forEach(slot => {
        const option = document.createElement("option");
        option.value = slot.value;
        option.textContent = slot.label;
        slotSelect.appendChild(option);
      });
      slotSelect.value = "";
      slotSelect.disabled = true;
      submit.disabled = true;
    };

    const updateAvailability = async () => {
      const doctorId = doctorSelect?.value || "";
      const selectedDate = dateInput?.value || "";
      const sequence = ++requestSequence;
      if (!doctorId || !selectedDate) {
        resetSlots("Choose doctor and date first");
        feedback.textContent = "Select a doctor and date to check available slots.";
        return;
      }

      resetSlots("Checking availability…");
      feedback.textContent = "Checking the doctor's booked slots…";
      try {
        const url = new URL(availabilityUrl, window.location.origin);
        url.searchParams.set("doctor_id", doctorId);
        url.searchParams.set("date", selectedDate);
        const response = await fetch(url.toString(), {
          headers: { "Accept": "application/json" },
          credentials: "same-origin"
        });
        const result = await response.json();
        if (sequence !== requestSequence) return;
        if (!response.ok) throw new Error(result.error || "Availability could not be checked.");

        const booked = new Set(result.booked_slots || []);
        const selectedTime = new Date();
        const currentLocalTime = String(selectedTime.getHours()).padStart(2, "0") + ":" +
          String(selectedTime.getMinutes()).padStart(2, "0");
        let availableCount = 0;
        slotSelect.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = "Choose an available slot";
        slotSelect.appendChild(placeholder);

        originalSlotOptions.forEach(slot => {
          const passedToday = selectedDate === localDate && slot.value <= currentLocalTime;
          const isBooked = booked.has(slot.value);
          const option = document.createElement("option");
          option.value = slot.value;
          option.disabled = isBooked || passedToday;
          option.textContent = slot.label + (isBooked ? " · Booked" : passedToday ? " · Time passed" : "");
          if (!option.disabled) availableCount += 1;
          slotSelect.appendChild(option);
        });
        slotSelect.disabled = availableCount === 0;
        submit.disabled = true;
        feedback.textContent = availableCount
          ? availableCount + " OPD slots available. Booked times are disabled."
          : "No future slots are available for this doctor on that date. Choose another date.";
      } catch (error) {
        if (sequence !== requestSequence) return;
        resetSlots("Availability unavailable");
        feedback.textContent = error.message || "Could not check availability. Refresh and try again.";
      }
    };

    doctorSelect?.addEventListener("change", updateAvailability);
    dateInput?.addEventListener("change", updateAvailability);
    slotSelect?.addEventListener("change", () => {
      submit.disabled = !slotSelect.value;
    });
    appointmentForm.addEventListener("submit", event => {
      if (!doctorSelect.value || !dateInput.value || !slotSelect.value) {
        event.preventDefault();
        feedback.textContent = "Choose a doctor, date and available time before submitting.";
      }
    });
  }

  document.querySelectorAll("form[onsubmit]").forEach(form => {
    form.addEventListener("submit", event => {
      if (form.dataset.confirmed === "yes") return;
    });
  });
});
