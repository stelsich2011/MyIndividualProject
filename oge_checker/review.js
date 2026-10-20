const data = JSON.parse(document.getElementById('data').textContent);
const fields = data.pages.flatMap(page => page.fields);
const rows = new Map();
for (const row of document.querySelectorAll('tr[data-id]')) rows.set(row.dataset.id, row);
function progress() {
  const count = fields.filter(field => rows.get(field.id).querySelector('.verified').checked).length;
  document.getElementById('progress').textContent = `Проверено полей: ${count}/${fields.length}`;
}
for (const field of fields) {
  const row = rows.get(field.id);
  row.querySelector('.ocr').textContent = `${field.raw_text || '(нет текста)'}\nУверенность модели: ${field.confidence === null ? 'нет' : field.confidence.toFixed(3)}`;
  if (field.adjustments?.length) {
    row.querySelector('.ocr').textContent += `\nКандидат после проверки запятой: ${field.candidate}`;
  }
  row.querySelector('.value').value = field.corrected_text ?? field.candidate;
  row.querySelector('.verified').checked = field.reviewed === true;
  row.querySelector('.value').addEventListener('input', () => {
    row.querySelector('.verified').checked = false;
    progress();
  });
  row.querySelector('.verified').addEventListener('change', progress);
}
progress();
document.getElementById('download').addEventListener('click', () => {
  const result = {
    schema_version: 1, source_id: data.source_id,
    fields: fields.map(field => ({
      id: field.id, raw_text: field.raw_text, candidate: field.candidate,
      corrected_text: rows.get(field.id).querySelector('.value').value,
      reviewed: rows.get(field.id).querySelector('.verified').checked
    }))
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'corrections.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.getElementById('import').addEventListener('change', async event => {
  try {
    const saved = JSON.parse(await event.target.files[0].text());
    if (saved.source_id !== data.source_id || !Array.isArray(saved.fields)) throw Error('Правки относятся к другому набору сканов');
    const ids = new Set();
    for (const field of saved.fields) {
      if (!rows.has(field.id) || ids.has(field.id) || typeof field.corrected_text !== 'string' || typeof field.reviewed !== 'boolean') {
        throw Error('Неверный формат полей правок');
      }
      ids.add(field.id);
    }
    for (const field of saved.fields) {
      rows.get(field.id).querySelector('.value').value = field.corrected_text;
      rows.get(field.id).querySelector('.verified').checked = field.reviewed;
    }
    progress();
  } catch (error) {
    alert(`Не удалось загрузить правки: ${error.message}`);
  }
});
