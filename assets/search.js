(() => {
  const input = document.querySelector('#search');
  if (!input) return;
  const rows = [...document.querySelectorAll('.search-row')];
  input.addEventListener('input', () => {
    const needle = input.value.trim().toLocaleLowerCase();
    let count = 0;
    for (const row of rows) {
      row.hidden = !row.textContent.toLocaleLowerCase().includes(needle);
      if (!row.hidden) count++;
    }
    document.querySelector('#search-state').textContent = needle ? `${count}개 행이 검색되었습니다. 항목별 건수는 전체 기준입니다.` : '';
  });
})();
