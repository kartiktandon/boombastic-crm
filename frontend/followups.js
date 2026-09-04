function followupTabRow(lead, completed = false) {
  const dateValue = completed ? (lead.last_follow_up_completed_at || lead.next_follow_up) : lead.next_follow_up;
  const date = dateValue ? new Date(dateValue) : null;
  const validDate = date && !Number.isNaN(date.getTime());
  const phone = String(lead.phone || "").replace(/\D/g, "");
  return `<tr>
    <td><div class="mini-contact"><span>${initials(lead.name)}</span><b>${esc(lead.name)}<small>${esc(lead.phone || "—")}</small></b></div></td>
    <td>${esc(lead.phone || "—")}</td><td>${esc(lead.service || lead.campaign || "Event")}</td>
    <td>${validDate ? `<b>${date.toLocaleDateString("en-GB", {day:"2-digit", month:"short", year:"numeric"})}</b><small>${date.toLocaleTimeString("en-US", {hour:"2-digit", minute:"2-digit"})}</small>` : `<span class="meta">No follow-up scheduled</span>`}</td>
    <td>${esc(lead.assigned_to || "Admin User")}</td><td><span class="priority ${lead.temperature || "warm"}">${nice(lead.temperature || "warm")}</span></td>
    <td><div class="follow-actions"><a href="tel:${esc(lead.phone || "")}">☎ Call</a>${phone ? `<a class="wa" href="https://wa.me/${phone}" target="_blank" rel="noreferrer">WhatsApp</a>` : ""}${completed ? `<button data-follow-view="${lead._id}">View Lead</button>` : `<button data-follow-done="${lead._id}">✓ Done</button><button data-follow-reschedule="${lead._id}">▣ Reschedule</button>`}</div></td>
  </tr>`;
}

followups = async function () {
  const data = await api("/leads/?limit=100"), all = data.items || [];
  state.leads = all;
  const now = new Date(), dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()), tomorrow = new Date(dayStart);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const scheduled = all.filter(lead => lead.next_follow_up);
  const groups = {
    today: scheduled.filter(lead => new Date(lead.next_follow_up) >= dayStart && new Date(lead.next_follow_up) < tomorrow),
    upcoming: scheduled.filter(lead => new Date(lead.next_follow_up) >= tomorrow),
    overdue: scheduled.filter(lead => new Date(lead.next_follow_up) < dayStart && !["won", "meeting_done", "lost"].includes(lead.status)),
    completed: all.filter(lead => lead.last_follow_up_completed_at || ["won", "meeting_done"].includes(lead.status))
  };
  let active = "today", query = "";
  shell(`<div class="follow-head"><div><h1>Follow-ups</h1><p>Stay on top of every conversation.</p></div></div>
    <div class="follow-metrics">${[["▣",groups.today.length,"DUE TODAY"],["◷",groups.overdue.length,"OVERDUE"],["▤",groups.upcoming.length,"UPCOMING"],["✓",groups.completed.length,"COMPLETED"],["×",all.length-scheduled.length,"NO FOLLOW-UP"]].map(([icon,count,label],index) => `<div class="follow-metric fm${index}"><i>${icon}</i><b>${count}</b><small>${label}</small></div>`).join("")}</div>
    <section class="follow-panel"><div class="follow-toolbar"><div class="follow-tabs">${[["today","Today"],["upcoming","Upcoming"],["overdue","Overdue"],["completed","Completed"]].map(([key,label]) => `<button type="button" data-follow-tab="${key}" class="${key === active ? "active" : ""}">${label}<b>${groups[key].length}</b></button>`).join("")}</div><label>⌕ <input id="follow-search" placeholder="Search by name, phone or event..."/></label><button class="btn primary" id="schedule-follow">＋ Schedule Follow-up</button></div>
    <div class="follow-layout"><div class="follow-table-wrap"><table class="follow-table"><thead><tr><th>Customer</th><th>Contact</th><th>Event Type</th><th>Follow-up Date & Time</th><th>Assigned To</th><th>Priority</th><th>Action</th></tr></thead><tbody id="follow-rows"></tbody></table></div><aside class="schedule-side"><div class="mini-calendar"><header><b>${now.toLocaleDateString("en-US", {month:"long",year:"numeric"})}</b></header><div class="week">S M T W T F S</div><div class="days">${Array.from({length:35},(_,i) => `<span class="${i+1 === now.getDate() ? "today" : ""}">${i < 31 ? i+1 : ""}</span>`).join("")}</div></div><div class="today-list"><h3>Today's Schedule</h3>${groups.today.slice(0,5).map(lead => `<div><time>${new Date(lead.next_follow_up).toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit"})}</time><span><b>${esc(lead.name)}</b><small>${esc(lead.service || "Follow-up")}</small></span></div>`).join("") || `<p class="empty">Nothing due today.</p>`}</div></aside></div></section>`);

  const draw = () => {
    const rows = groups[active].filter(lead => [lead.name,lead.phone,lead.service,lead.campaign].some(value => String(value || "").toLowerCase().includes(query)));
    document.querySelector("#follow-rows").innerHTML = rows.length ? rows.map(lead => followupTabRow(lead, active === "completed")).join("") : `<tr><td colspan="7" class="empty">No ${active} follow-ups found.</td></tr>`;
    document.querySelectorAll("[data-follow-done]").forEach(button => button.onclick = async () => { await api("/leads/" + button.dataset.followDone, {method:"PATCH", body:JSON.stringify({next_follow_up:null,last_follow_up_completed_at:new Date().toISOString()})}); say("Follow-up completed"); followups(); });
    document.querySelectorAll("[data-follow-reschedule]").forEach(button => button.onclick = () => followupModal(all, button.dataset.followReschedule));
    document.querySelectorAll("[data-follow-view]").forEach(button => button.onclick = () => leadDetail(button.dataset.followView));
  };
  document.querySelectorAll("[data-follow-tab]").forEach(button => button.onclick = () => { active = button.dataset.followTab; document.querySelectorAll("[data-follow-tab]").forEach(item => item.classList.toggle("active", item === button)); draw(); });
  document.querySelector("#follow-search").oninput = event => { query = event.target.value.trim().toLowerCase(); draw(); };
  document.querySelector("#schedule-follow").onclick = () => all.length ? followupModal(all) : say("Add a lead first");
  draw();
};

followupModal = function (leads, selected="") {
  modal("Schedule Follow-up", `<div class="formgrid"><div class="field full"><label>Lead</label><select name="lead_id">${leads.map(lead => `<option value="${lead._id}" ${lead._id === selected ? "selected" : ""}>${esc(lead.name)}</option>`).join("")}</select></div><div class="field full"><label>Follow-up Date & Time</label><input name="next_follow_up" type="datetime-local" required/></div></div>`, async data => {
    const values = Object.fromEntries(data);
    await api("/leads/" + values.lead_id, {method:"PATCH", body:JSON.stringify({next_follow_up:values.next_follow_up,last_follow_up_completed_at:null})});
    say("Follow-up scheduled"); followups();
  });
};
