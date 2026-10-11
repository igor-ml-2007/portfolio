const gallery = document.querySelector('#gallery');
const featuredGallery = document.querySelector('#featuredGallery');
const galleryDialog = document.querySelector('#galleryDialog');
const infoPanel = document.querySelector('#infoPanel');
const panelShade = document.querySelector('#panelShade');
const count = document.querySelector('#workCount');
const heroImage = document.querySelector('#heroImage');
const artistImage = document.querySelector('#artistImage');

const escapeHtml = value => String(value || '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
const workMarkup = (work, index, compact = false) => {
  const number = String(index + 1).padStart(2, '0');
  const image = escapeHtml(work.image || '');
  const slot = `<div class="art work-template static-slot"><img src="${image}" alt="${escapeHtml(work.title)}" /><span>${number}</span><small>${image.replace(/^\//, '') || 'photos/ваша-работа.jpg'}</small></div>`;
  return `<article class="work-card ${escapeHtml(work.format || 'square')} ${escapeHtml(work.category || 'painting')}" data-category="${escapeHtml(work.category || 'painting')}">${slot}<div class="work-meta"><div><h3>${escapeHtml(work.title)}</h3><p>${escapeHtml(work.material || 'Авторская работа')} · ${escapeHtml(work.year)}</p></div><span>${number}</span></div></article>`;
};

function activateImages(root = document) {
  root.querySelectorAll('.static-slot img').forEach(image => {
    const showImage = () => image.closest('.static-slot').classList.add('has-photo');
    image.addEventListener('load', showImage, { once: true });
    if (image.complete && image.naturalWidth) showImage();
  });
}
function updateCount() {
  count.textContent = String(gallery.querySelectorAll('.work-card:not(.is-hidden)').length).padStart(2, '0');
}
function renderWorks(works) {
  gallery.innerHTML = works.map((work, index) => workMarkup(work, index)).join('');
  const featured = works.filter(work => work.featured).slice(0, 3);
  featuredGallery.innerHTML = (featured.length ? featured : works.slice(0, 3)).map((work, index) => workMarkup(work, index, true)).join('');
  activateImages(gallery);
  activateImages(featuredGallery);
  updateCount();
}
async function loadWorks() {
  try {
    const response = await fetch('content/gallery.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Gallery unavailable');
    const data = await response.json();
    if (data.heroImage) {
      heroImage.src = data.heroImage;
      heroImage.closest('.cover-placeholder').querySelector('.placeholder-mark').textContent = data.heroImage.replace(/^\//, '');
    }
    if (data.artistImage) {
      artistImage.src = data.artistImage;
      artistImage.closest('.about-image').querySelector('.artist-path').textContent = data.artistImage.replace(/^\//, '');
    }
    if (Array.isArray(data.works) && data.works.length) renderWorks(data.works);
  } catch {
    // Local file preview keeps the static gallery already present in index.html.
    activateImages();
    updateCount();
  }
}

document.querySelector('#openGallery').addEventListener('click', () => galleryDialog.showModal());
document.querySelector('#closeGallery').addEventListener('click', () => galleryDialog.close());
galleryDialog.addEventListener('click', event => { if (event.target === galleryDialog) galleryDialog.close(); });
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-filter]').forEach(item => item.classList.toggle('active', item === button));
  gallery.querySelectorAll('.work-card').forEach(card => card.classList.toggle('is-hidden', button.dataset.filter !== 'all' && card.dataset.category !== button.dataset.filter));
  updateCount();
}));

function closeInfo() {
  infoPanel.classList.remove('open');
  panelShade.classList.remove('open');
  infoPanel.setAttribute('aria-hidden', 'true');
}
document.querySelector('#openInfo').addEventListener('click', () => {
  infoPanel.classList.add('open');
  panelShade.classList.add('open');
  infoPanel.setAttribute('aria-hidden', 'false');
});
document.querySelector('#closeInfo').addEventListener('click', closeInfo);
panelShade.addEventListener('click', closeInfo);

const observer = new IntersectionObserver(entries => entries.forEach(entry => {
  if (entry.isIntersecting) entry.target.classList.add('visible');
}), { threshold: .12 });
document.querySelectorAll('.reveal').forEach(element => observer.observe(element));
loadWorks();
