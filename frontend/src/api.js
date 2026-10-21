export async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {...options, headers:{'Content-Type':'application/json',...options.headers}});
  let data;
  try { data = await response.json(); } catch { throw new Error('The server returned an unreadable response. Check that Flask is running.'); }
  if (!response.ok) throw new Error(data.message || 'Request failed');
  return data;
}
export const post = (path, data={}) => api(path,{method:'POST',body:JSON.stringify(data)});
export function downloadUrl(format,group='') {const p=new URLSearchParams({format});if(group)p.set('group',group);return `/api/export?${p}`;}
export const formatValue = (n, unit='', digits=1) => n == null ? 'not enough variation' : `${Number(n).toFixed(digits)}${unit}`;
export const percent = n => n == null ? 'not enough variation' : `${(n*100).toFixed(1)}%`;
