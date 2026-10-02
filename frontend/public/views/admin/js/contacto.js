// Datos de contacto que se muestran al pie de la tienda.

// --- datos de contacto ---
const contactForm = $("contact-form");
function renderContact() {
  for (const input of contactForm.querySelectorAll("input")) input.value = status.contact[input.name] || "";
}
contactForm.oninput = () => $("contact-error").textContent = "";
contactForm.onsubmit = async e => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(contactForm));
  try {
    status.contact = (await api("/api/admin/contact", { method: "PUT", body })).contact;
    renderContact();
    toast.fire({ icon: "success", title: "Datos de contacto guardados" });
  } catch (err) {
    if (err.status === 401) return showGate();
    $("contact-error").textContent = err.message;
  }
};
