(function () {
  const main = document.querySelector('main');
  if (!main) return;
  const nav = document.createElement('nav');
  nav.className = 'gene-detail-nav';
  nav.setAttribute('aria-label', 'Gene detail sections');
  [
    ['.go-panel', 'goAnnotations', 'GO'],
    ['.domain-panel', 'domainAnnotations', 'Protein Domains'],
    ['.transcript-panel', 'transcriptAnnotations', 'Transcripts'],
    ['#blastCard', 'blastCard', 'BLAST'],
    ['#panGenomeCard', 'panGenomeCard', 'Pan-genome'],
    ['#orthologCard', 'orthologCard', 'Ortholog']
  ].forEach(([selector, id, label]) => {
    const target = document.querySelector(selector);
    if (!target) return;
    target.id = id;
    target.style.scrollMarginTop = '24px';
    const link = document.createElement('a');
    link.href = '#' + id;
    link.textContent = label;
    nav.appendChild(link);
  });
  main.prepend(nav);
  const exportButton = document.createElement('button');
  exportButton.type = 'button';
  exportButton.className = 'gene-action-button gene-export-button';
  exportButton.textContent = 'Export annotations CSV';
  nav.appendChild(exportButton);
  const status = document.createElement('span');
  status.setAttribute('role', 'status');
  nav.appendChild(status);
  let loaded;
  function annotationsLoaded(data) {
    loaded = data;
    document.querySelectorAll('.go-panel .go-category').forEach(panel => {
      const heading = panel.querySelector('h4');
      const list = panel.querySelector('ul');
      if (!heading || !list || heading.querySelector('button')) return;
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.style.cssText = 'font:inherit;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-align:left';
      toggle.textContent = heading.textContent + ' (' + list.querySelectorAll('li:not(.annotation-empty)').length + ')';
      toggle.setAttribute('aria-expanded', 'true');
      toggle.setAttribute('aria-controls', list.id);
      toggle.onclick = () => {
        list.hidden = !list.hidden;
        toggle.setAttribute('aria-expanded', String(!list.hidden));
      };
      heading.replaceChildren(toggle);
    });
  }
  document.addEventListener('gene-annotations-loaded', event => annotationsLoaded(event.detail));
  if (window.maizeGeneAnnotations) annotationsLoaded(window.maizeGeneAnnotations);
  exportButton.onclick = () => {
    const rows = [];
    const gene = loaded?.gene?.gene_id || '';
    [['go', 'GO', 'go_id'], ['protein_domains', 'Protein Domain', 'domain_id'],
      ['transcripts', 'Transcript', 'transcript_id']].forEach(([key, type, id]) => {
      (loaded?.[key] || []).forEach(item => rows.push([
        gene, type, item[id] || item.id || '', item.description || item.name || '',
        item.source_id || '', item.chromosome ?? '', item.start ?? '', item.end ?? '',
        JSON.stringify(item)
      ]));
    });
    if (!rows.length) { status.textContent = 'No loaded annotations to export.'; return; }
    const cell = value => '"' + String(value).replace(/"/g, '""') + '"';
    const csv = [['Gene ID', 'Annotation type', 'Annotation ID', 'Description', 'Source',
      'Chromosome', 'Start', 'End', 'Original fields (JSON)'], ...rows]
      .map(row => row.map(cell).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\uFEFF', csv], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = (gene || 'gene') + '-annotations.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status.textContent = 'Exported ' + rows.length + ' annotations.';
  };
})();
