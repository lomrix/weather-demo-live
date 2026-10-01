const zone = 'Europe/Oslo';
const parts = d => Object.fromEntries(new Intl.DateTimeFormat('en-GB', {timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23'}).formatToParts(d).map(p => [p.type, p.value]));
const key = p => `${p.year}-${p.month}-${p.day}`;
function tomorrow() {
  const p = parts(new Date());
  const date = new Date(Date.UTC(+p.year, +p.month - 1, +p.day + 1, 12));
  return {key: key(parts(date)), date};
}
function weather(code = '') {
  const name = code.replace(/_(day|night|polartwilight)$/, '');
  const icon = name.includes('thunder') ? '⛈️' : /snow|sleet/.test(name) ? '🌨️' : name.includes('rain') ? '🌧️' : name === 'clearsky' ? '☀️' : name === 'fair' ? '🌤️' : name === 'partlycloudy' ? '⛅' : name === 'fog' ? '🌫️' : '☁️';
  const label = name.replace(/heavyrain/g,'heavy rain').replace(/lightrain/g,'light rain').replace(/partlycloudy/g,'partly cloudy').replace(/clearsky/g,'clear sky').replace(/showers/g,' showers').replace(/and/g,' and ').replace(/^./, c => c.toUpperCase()) || 'Forecast';
  return {icon, label};
}
const summary = p => p.data.next_1_hours || p.data.next_6_hours || p.data.next_12_hours;
const set = (id, value) => document.getElementById(id).textContent = value;
async function load() {
  const button = document.getElementById('refresh'), status = document.getElementById('status');
  button.disabled = true; status.className = ''; status.textContent = 'Loading tomorrow’s forecast…';
  try {
    const response = await fetch('/api/forecast', {signal: AbortSignal.timeout(20000)});
    if (!response.ok) throw new Error('Forecast service unavailable');
    const data = await response.json(), target = tomorrow();
    set('date', new Intl.DateTimeFormat('en-GB', {timeZone: zone, weekday: 'long', day: 'numeric', month: 'long'}).format(target.date));
    const points = data.properties.timeseries.filter(p => key(parts(new Date(p.time))) === target.key);
    if (!points.length) throw new Error('Tomorrow unavailable');
    const nearest = hour => points.reduce((a,b) => Math.abs(+parts(new Date(a.time)).hour-hour) <= Math.abs(+parts(new Date(b.time)).hour-hour) ? a : b);
    const noon = nearest(12), details = noon.data.instant.details, w = weather(summary(noon)?.summary.symbol_code);
    const temperatures = points.map(p => p.data.instant.details.air_temperature);
    set('temperature', `${Math.round(details.air_temperature)}°`); set('condition', w.label); set('symbol', w.icon);
    set('range', `${Math.round(Math.min(...temperatures))}° / ${Math.round(Math.max(...temperatures))}°`);
    const complete = points.every(p => p.data.next_1_hours?.details.precipitation_amount !== undefined);
    set('rain', complete ? `${points.reduce((sum,p) => sum + p.data.next_1_hours.details.precipitation_amount, 0).toFixed(1)} mm` : 'Unavailable');
    set('wind', `${details.wind_speed.toFixed(1)} m/s`);
    const hours = document.getElementById('hours'); hours.replaceChildren();
    for (const [label,hour] of [['Morning',6],['Midday',12],['Afternoon',15],['Evening',21]]) {
      const p = nearest(hour), w = weather(summary(p)?.summary.symbol_code), card = document.createElement('div'); card.className = 'hour';
      const title = document.createElement('div'); title.textContent = `${label} · ${parts(new Date(p.time)).hour}:00`;
      const icon = document.createElement('div'); icon.className = 'icon'; icon.textContent = w.icon; icon.setAttribute('role','img'); icon.setAttribute('aria-label', w.label);
      const temp = document.createElement('strong'); temp.textContent = `${Math.round(p.data.instant.details.air_temperature)}°`;
      const rain = document.createElement('p'); rain.textContent = p.data.next_1_hours ? `${p.data.next_1_hours.details.precipitation_amount.toFixed(1)} mm rain / hour` : 'Rain unavailable';
      card.append(title,icon,temp,rain); hours.append(card);
    }
    document.getElementById('forecast').hidden = false; status.textContent = '';
    set('updated', `Updated ${new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit'}).format(new Date(data.properties.meta.updated_at))} · Oslo time`);
  } catch (error) {
    status.className = 'error'; status.textContent = 'Could not load tomorrow’s forecast. Please try refreshing in a moment.';
  } finally { button.disabled = false; }
}
document.getElementById('refresh').addEventListener('click', load);
load();
