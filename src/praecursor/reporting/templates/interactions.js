/* One press response for pointer and keyboard activation; no motion when reduced. */
document.addEventListener('click', event => {
  const button = event.target.closest('button, .button');
  if (!button || button.disabled || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const rect = button.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  const wave = document.createElement('span');
  wave.className = 'click-wave'; wave.setAttribute('aria-hidden', 'true');
  const x = event.detail ? event.clientX - rect.left : rect.width / 2;
  const y = event.detail ? event.clientY - rect.top : rect.height / 2;
  Object.assign(wave.style, {width:size+'px',height:size+'px',left:(x-size/2)+'px',top:(y-size/2)+'px'});
  button.append(wave); wave.addEventListener('animationend', () => wave.remove(), {once:true});
});
let toastTimer;
function notifyUser(message) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  clearTimeout(toastTimer); toast.textContent = message; toast.classList.add('visible');
  toastTimer = setTimeout(() => toast.classList.remove('visible'), 4500);
}
