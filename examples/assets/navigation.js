const slides = [...document.querySelectorAll('.slide')];
let index = 0;
function show(i) {
  index = Math.max(0, Math.min(slides.length - 1, i));
  slides.forEach((slide, n) => {
    slide.hidden = n !== index;
    slide.classList.toggle('active', n === index);
  });
}
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.code === 'Space') show(index + 1);
  if (e.key === 'ArrowLeft') show(index - 1);
  if (e.key === 'Home') show(0);
});
show(0);
