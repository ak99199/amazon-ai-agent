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

document.querySelectorAll(".ads-historical-sync-button").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("This will create and download a read-only Amazon Ads historical report and store validated performance data locally. It will not modify campaigns, bids, budgets, keywords, or targeting. Continue?")) return;
    const panel=button.closest(".ads-historical-sync"),resultNode=panel.querySelector(".ads-historical-sync-result");button.disabled=true;resultNode.textContent="Historical sync running...";
    try {
      const response=await fetch("/api/ads/manual-historical-sync",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm_live_read:true})});
      const result=await response.json();resultNode.textContent=response.ok ? `${result.status}: ${result.rows_persisted} row(s) persisted. ${result.message}` : (result.detail||"Historical sync failed safely.");
      await Promise.all([fetch("/api/ads/historical-sync-health"),fetch("/api/ads/historical-sync-runs?limit=10")]);
      if(response.ok) window.location.reload(); else button.disabled=false;
    } catch (_) {resultNode.textContent="Historical sync status unavailable.";button.disabled=false;}
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

document.querySelectorAll(".ads-live-targeting-validation").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Run bounded, read-only campaign, ad group, keyword, target, and relationship validation?")) return;
    const panel=button.closest(".ads-live-readiness");
    const response=await fetch("/api/ads/live-targeting-validation",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm_live_read:true})});
    const result=await response.json();
    if(response.ok) window.alert(`Campaigns ${result.campaigns.records_valid}/${result.campaigns.records_received}; ad groups ${result.ad_groups.records_valid}/${result.ad_groups.records_received}; keywords ${result.keywords.records_valid}/${result.keywords.records_received}; targets ${result.targets.records_valid}/${result.targets.records_received}; relationships ${result.relationships.valid} valid, ${result.relationships.invalid} invalid, ${result.relationships.unresolved} unresolved due to bounded validation.`); else window.alert(result.detail||"Live targeting validation is unavailable.");
  });
});

document.querySelectorAll(".ads-live-report-lifecycle-validation").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Create one bounded, read-only historical Amazon Ads reporting job and validate its lifecycle?")) return;
    const panel=button.closest(".ads-live-readiness");
    const response=await fetch("/api/ads/live-report-lifecycle-validation",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm_live_read:true})});
    const result=await response.json();
    if(response.ok) window.alert(`Report ${result.report_kind}; ${result.start_date} to ${result.end_date}; creation ${result.creation_attempted ? "yes" : "no"}; polls ${result.poll_attempts}; last status ${result.last_report_status}; terminal ${result.terminal ? "yes" : "no"}; download ready ${result.download_ready ? "yes" : "no"}.`); else window.alert(result.detail||"Historical report lifecycle validation is unavailable.");
  });
});

document.querySelectorAll(".ads-live-report-download-validation").forEach(button => {
  button.addEventListener("click", async () => {
    if (!window.confirm("Create and download one bounded, read-only historical Amazon Ads report for structural validation?")) return;
    const panel=button.closest(".ads-live-readiness");
    const response=await fetch("/api/ads/live-report-download-validation",{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":panel.dataset.csrf},body:JSON.stringify({confirm_live_read:true})});
    const result=await response.json();
    if(response.ok) window.alert(`Lifecycle ${result.last_report_status}; download ${result.download_succeeded ? "successful" : "not completed"}; decompression ${result.decompression_succeeded ? "successful" : "not completed"}; parsing ${result.parse_succeeded ? "successful" : "not completed"}; rows observed ${result.rows_observed}, valid ${result.rows_valid}, invalid ${result.rows_invalid}; truncated ${result.rows_truncated ? "yes" : "no"}.`); else window.alert(result.detail||"Historical report download validation is unavailable.");
  });
});
