document.querySelectorAll("table tbody tr").forEach(row => row.dataset.ready = "true");

document.querySelectorAll(".ads-decision").forEach(form => {
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.submitter;
    if (!button) return;
    const panel = form.closest(".ads-action-center");
    const response = await fetch(`/api/ads/actions/${encodeURIComponent(form.dataset.recommendationId)}/decision`, {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRF-Token": panel.dataset.csrf},
      body: JSON.stringify({status: button.dataset.status, review_note: form.elements.review_note.value})
    });
    if (response.ok) window.location.reload();
  });
});
