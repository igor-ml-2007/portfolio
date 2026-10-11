const worksRoot = document.querySelector('#works');
const statusBox = document.querySelector('#status');
const heroPreview = document.querySelector('#heroPreview');
const artistPreview = document.querySelector('#artistPreview');
const heroUpload = document.querySelector('#heroUpload');
const artistUpload = document.querySelector('#artistUpload');
let works = [];
let heroImage = '';
let artistImage = '';

const notify = message => {
  statusBox.textContent = message;
  statusBox.classList.add('show');
  setTimeout(() => statusBox.classList.remove('show'), 2800);
};

const loginIfNeeded = response => {
  if (response.status === 401) {
    location.assign('/admin/login.html');
    return true;
  }
  return false;
};

const requestError = async response => {
  try {
    return (await response.json()).error || 'Операция не выполнена';
  } catch {
    return 'Операция не выполнена';
  }
};

const options = (value, items) => items.map(([label, key]) =>
  `<option value="${key}" ${value === key ? 'selected' : ''}>${label}</option>`
).join('');

function render() {
  worksRoot.innerHTML = works.map((work, index) => `
    <article class="work" data-index="${index}">
      <img class="preview" src="${work.image || ''}" alt="">
      <div>
        <div class="fields">
          <label>Название<input data-key="title" value="${work.title || ''}"></label>
          <label>Год<input data-key="year" value="${work.year || ''}"></label>
          <label>Материал<input data-key="material" value="${work.material || ''}"></label>
          <label>Категория<select data-key="category">${options(work.category, [['Живопись', 'painting'], ['Графика', 'graphic'], ['Объекты', 'object']])}</select></label>
          <label>Формат<select data-key="format">${options(work.format, [['Вертикальный', 'tall'], ['Квадрат', 'square'], ['Горизонтальный', 'wide']])}</select></label>
        </div>
        <div class="options">
          <label><input type="checkbox" data-key="featured" ${work.featured ? 'checked' : ''}> На главной странице</label>
          <label class="upload">Заменить фото<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden></label>
        </div>
      </div>
      <button class="remove" type="button" title="Удалить работу">×</button>
    </article>`).join('');
  document.querySelector('#workTotal').textContent = `Работ в портфолио: ${works.length}`;
}

async function load() {
  const response = await fetch('/api/gallery', { credentials: 'same-origin' });
  if (loginIfNeeded(response)) return;
  if (!response.ok) throw Error(await requestError(response));
  const data = await response.json();
  works = data.works || [];
  heroImage = data.heroImage || '';
  artistImage = data.artistImage || '';
  heroPreview.src = heroImage;
  artistPreview.src = artistImage;
  render();
}

worksRoot.addEventListener('input', event => {
  const card = event.target.closest('.work');
  if (!card || !event.target.dataset.key) return;
  works[card.dataset.index][event.target.dataset.key] = event.target.type === 'checkbox'
    ? event.target.checked : event.target.value;
});

worksRoot.addEventListener('change', async event => {
  const card = event.target.closest('.work');
  const file = event.target.files && event.target.files[0];
  if (!card || event.target.type !== 'file' || !file) return;
  const form = new FormData();
  form.append('image', file);
  notify('Загружаю фото…');
  try {
    const response = await fetch('/api/upload', { method: 'POST', credentials: 'same-origin', body: form });
    if (loginIfNeeded(response)) return;
    if (!response.ok) throw Error(await requestError(response));
    works[card.dataset.index].image = (await response.json()).path;
    render();
    notify('Фото добавлено. Нажмите «Сохранить изменения».');
  } catch (error) {
    notify(error.message || 'Не удалось загрузить фото');
  }
});

worksRoot.addEventListener('click', event => {
  const card = event.target.closest('.work');
  if (card && event.target.matches('.remove')) {
    works.splice(Number(card.dataset.index), 1);
    render();
  }
});

document.querySelector('#addWork').onclick = () => {
  works.push({ title: 'Новая работа', year: String(new Date().getFullYear()), material: 'Материал', category: 'painting', format: 'square', image: '', featured: false });
  render();
};

document.querySelector('#save').onclick = async () => {
  try {
    const response = await fetch('/api/gallery', {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ works, heroImage, artistImage }),
    });
    if (loginIfNeeded(response)) return;
    if (!response.ok) throw Error(await requestError(response));
    notify('Галерея сохранена');
  } catch (error) {
    notify(error.message || 'Не удалось сохранить изменения');
  }
};

async function uploadImage(file, type) {
  const form = new FormData();
  form.append('image', file);
  notify('Загружаю фото…');
  try {
    const response = await fetch('/api/upload', { method: 'POST', credentials: 'same-origin', body: form });
    if (loginIfNeeded(response)) return null;
    if (!response.ok) throw Error(await requestError(response));
    return (await response.json()).path;
  } catch (error) {
    notify(error.message || 'Не удалось загрузить фото');
    return null;
  }
}

heroUpload.addEventListener('change', async event => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const path = await uploadImage(file, 'hero');
  if (path) {
    heroImage = path;
    heroPreview.src = path;
    notify('Фото загружено. Нажмите «Сохранить изменения».');
  }
});

artistUpload.addEventListener('change', async event => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  const path = await uploadImage(file, 'artist');
  if (path) {
    artistImage = path;
    artistPreview.src = path;
    notify('Фото загружено. Нажмите «Сохранить изменения».');
  }
});

load().catch(error => notify(error.message || 'Не удалось загрузить галерею'));
