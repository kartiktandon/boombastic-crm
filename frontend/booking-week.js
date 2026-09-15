// A local-time weekly schedule. Existing month and list views remain available.
const originalBookings = bookings;
let bookingWeekDate = new Date();
state.bookingView = "week";

function weekStart(date) {
  const start = new Date(date);
  start.setDate(start.getDate() - start.getDay());
  start.setHours(0, 0, 0, 0);
  return start;
}

function weekSegments(items, day) {
  const end = new Date(day); end.setDate(end.getDate() + 1);
  const segments = items.flatMap(item => {
    const start = new Date(item.scheduled_at);
    const finish = new Date(start.getTime() + Number(item.duration_minutes || 30) * 60000);
    if (!(start < end && finish > day)) return [];
    const from = start < day ? 0 : start.getHours() * 60 + start.getMinutes();
    const to = finish >= end ? 1440 : finish.getHours() * 60 + finish.getMinutes();
    return [{item, start, finish, from, to, lane: 0, lanes: 1}];
  }).sort((a,b) => a.from-b.from || b.to-a.to);
  let group = [], groupEnd = -1, laneEnds = [];
  const closeGroup = () => group.forEach(event => event.lanes = laneEnds.length);
  for (const event of segments) {
    if (event.from >= groupEnd) { closeGroup(); group = []; laneEnds = []; groupEnd = -1; }
    let lane = laneEnds.findIndex(end => end <= event.from);
    if (lane < 0) lane = laneEnds.length;
    laneEnds[lane] = event.to; event.lane = lane;
    group.push(event); groupEnd = Math.max(groupEnd,event.to);
  }
  closeGroup();
  return segments;
}

function bookingWeek(items, leads) {
  const start = weekStart(bookingWeekDate), now = new Date();
  const days = Array.from({length:7}, (_,i) => { const day=new Date(start); day.setDate(day.getDate()+i); return day; });
  const time = date => date.toLocaleTimeString([], {hour:"numeric",minute:"2-digit"});
  const label = date => date.toLocaleDateString([], {month:"short",day:"numeric",year:"numeric"});
  const visibleEvents = days.flatMap(day => weekSegments(items, day));
  const firstHour = Math.min(8, ...visibleEvents.map(event => Math.floor(event.from / 60)));
  const lastHour = Math.max(20, ...visibleEvents.map(event => Math.ceil(event.to / 60)));
  const offset = firstHour * 60;
  return `<section class="week-calendar"><header><div><h2>${label(days[0])} – ${label(days[6])}</h2><p>Times shown in ${esc(Intl.DateTimeFormat().resolvedOptions().timeZone)}</p></div></header><div class="week-scroll"><div class="week-canvas"><div class="week-day-head"><span>Time</span>${days.map(day=>`<div class="${day.toDateString()===now.toDateString()?"is-today":""}"><span>${day.toLocaleDateString([],{weekday:"short"})}</span><b>${day.getDate()}</b></div>`).join("")}</div><div class="week-body" style="height:${(lastHour-firstHour)*60}px"><div class="week-hours">${Array.from({length:lastHour-firstHour},(_,index)=>{const hour=firstHour+index;return `<span style="top:${(hour-firstHour)*60}px">${hour===0?"12 AM":hour<12?hour+" AM":hour===12?"12 PM":hour-12+" PM"}</span>`}).join("")}</div>${days.map(day=>`<div class="week-day" aria-label="${label(day)}">${weekSegments(items,day).map(event=>{
    const lead=leads.find(lead=>lead._id===event.item.lead_id);
    const details=bookingDisplayDetails(event.item,lead);
    const description=`${event.item.title} · Host: ${details.host} · ${details.timing} · Area: ${details.area} · ${details.people} people · Remark: ${details.remark}`;
    return `<div class="week-event-slot" style="top:${event.from-offset}px;height:${Math.max(event.to-event.from,15)}px;left:calc(${event.lane/event.lanes*100}% + 2px);width:calc(${100/event.lanes}% - 4px)"><button class="week-event ${event.item.status==="cancelled"?"is-cancelled":event.item.status==="completed"?"is-completed":""}" data-edit-booking="${esc(event.item._id)}" aria-label="${esc(description)}"><strong>${esc(event.item.title)}</strong><span class="week-event-timing">${esc(details.timing)}</span><small><b>Host Name:</b> ${esc(details.host)}</small><small><b>Area:</b> ${esc(details.area)}</small><small><b>No. of People:</b> ${esc(details.people)}</small><small class="week-event-remark"><b>Remark:</b> ${esc(details.remark)}</small></button></div>`;
  }).join("")}${day.toDateString()===now.toDateString()&&now.getHours()>=firstHour&&now.getHours()<lastHour?`<div class="week-now" style="top:${now.getHours()*60+now.getMinutes()-offset}px" aria-label="Current time"></div>`:""}</div>`).join("")}</div></div></div><p class="week-help">Booking details are shown inside each time block. Click a booking to edit it. Overlapping bookings appear side by side.</p></section>`;
}

bookings = async function() {
  if (state.bookingView !== "week") {
    await originalBookings();
    const tabs=document.querySelector(".booking-tabs");
    const button=document.createElement("button"); button.textContent="Week & Time";
    button.onclick=()=>{state.bookingView="week";bookings()}; tabs.prepend(button);
    tabs.querySelector('[data-booking-view="calendar"]').textContent="Month";
    return;
  }
  const [items, result]=await Promise.all([api("/meetings/"),dashboardLeads()]);
  const leads=result.items, ids=new Set(leads.map(lead=>lead._id));
  const scoped=state.businessUnit?items.filter(item=>ids.has(item.lead_id)):items;
  shell(`<div class="booking-head"><div class="booking-title-icon">▣</div><div><h1>Bookings</h1><p>Your team's schedule, hour by hour</p></div><button class="btn primary" id="newitem">＋ Schedule Booking</button></div><div class="booking-tabs"><button class="active" data-week-view="week">Week & Time</button><button data-week-view="calendar">Month</button><button data-week-view="list">List View</button></div>${bookingWeek(scoped,leads)}`);
  document.querySelectorAll("[data-week-view]").forEach(button=>button.onclick=()=>{state.bookingView=button.dataset.weekView;bookings()});
  const navigation=document.createElement("nav");
  navigation.setAttribute("aria-label","Week navigation");
  navigation.innerHTML='<button type="button" data-week-offset="-7">‹ Previous Week</button><button type="button" data-week-offset="7">Next Week ›</button>';
  document.querySelector(".week-calendar>header").append(navigation);
  navigation.querySelectorAll("button").forEach(button=>button.onclick=async()=>{
    navigation.querySelectorAll("button").forEach(control=>control.disabled=true);
    const previousDate=new Date(bookingWeekDate);
    bookingWeekDate.setDate(bookingWeekDate.getDate()+Number(button.dataset.weekOffset));
    try{await bookings()}catch(error){
      bookingWeekDate=previousDate;
      navigation.querySelectorAll("button").forEach(control=>control.disabled=false);
      say(error.message);
    }
  });
  document.querySelector("#newitem").onclick=()=>leads.length?meetingModal(leads):say("No leads found for this company");
  document.querySelectorAll("[data-edit-booking]").forEach(button=>button.onclick=()=>editMeetingModal(items.find(item=>item._id===button.dataset.editBooking),leads));
};
