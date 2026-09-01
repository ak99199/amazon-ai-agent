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

document.querySelectorAll(".dry-run").forEach(button => {
  button.addEventListener("click", async () => {
    const panel = button.closest(".ads-action-center");
    const response = await fetch(`/api/ads/actions/${encodeURIComponent(button.dataset.recommendationId)}/dry-run`, {
      method: "POST", headers: {"X-CSRF-Token": panel.dataset.csrf}
    });
    if (response.ok) window.location.reload();
  });
});

document.querySelectorAll(".ads-sync-button").forEach(button => {
  button.addEventListener("click", async () => {
    const panel=button.closest(".ads-sync");
    const response=await fetch("/api/ads/sync",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({window_days:7})});
    if(response.ok) window.location.reload();
  });
});

document.querySelectorAll(".rule-version-activate").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Activate this human-approved internal recommendation threshold version? This does not change Amazon Ads campaigns.")) return;
    const panel=button.closest(".ads-rule-versions");
    const response=await fetch(`/api/ads/rule-versions/${encodeURIComponent(button.dataset.ruleVersionId)}/activate`,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm:true,expected_active_rule_version_id:panel.dataset.activeId||null})});
    if(response.ok) window.location.reload(); else if(response.status===409) window.alert("The active rule version changed. Refresh and review before trying again.");
  });
});

document.querySelectorAll(".rule-version-rollback").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Rollback to the previous internal recommendation rule version recorded in activation history?")) return;
    const panel=button.closest(".ads-rule-versions");
    const response=await fetch("/api/ads/rule-versions/rollback",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm:true,expected_active_rule_version_id:panel.dataset.activeId||null})});
    if(response.ok) window.location.reload(); else if(response.status===409) window.alert("The active rule version changed. Refresh and review before trying again.");
  });
});

document.querySelectorAll(".ads-live-smoke-test").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Run a bounded Amazon Ads read-only smoke test? No campaigns, bids, budgets, keywords, or targeting will be modified.")) return;
    const panel=button.closest(".ads-live-readiness");
    const response=await fetch("/api/ads/live-smoke-test",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm_live_read:true})});
    const result=await response.json();window.alert(response.ok ? result.message : (result.detail||"Live smoke test is unavailable."));
  });
});

document.querySelectorAll(".ads-live-entity-validation").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Validate the configured Amazon Ads profile and perform one bounded, read-only campaign GET?")) return;
    const panel=button.closest(".ads-live-readiness");
    const response=await fetch("/api/ads/live-entity-validation",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm_live_read:true})});
    const result=await response.json();
    if(response.ok) window.alert(`Profile: ${result.profile.matched ? "Matched" : "Not Found"}. Campaigns — received ${result.campaigns.records_received}, valid ${result.campaigns.records_valid}, invalid ${result.campaigns.records_invalid}, duplicates ${result.campaigns.duplicate_count}.`); else window.alert(result.detail||"Live entity validation is unavailable.");
  });
});
