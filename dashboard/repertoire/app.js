(() => {
  const PLAYLIST_URL = '../data/repertoire/index.json?v=' + Date.now();
  const SONG_BASE = '../data/repertoire/';
  const PLAYLIST_ID = 'PLa7WXH9S8Er8';

  let playlist = [];
  let currentSong = null;
  let audioEl = null;
  let isPlaying = false;
  let playbackRate = 1.0;
  let originalBpm = null;
  let adjustedBpm = null;
  let loopA = null;
  let loopB = null;
  let loopEnabled = false;
  let teleAuto = true;
  let fontSize = 22;
  let darkMode = true;
  let practiceTimer = null;
  let practiceStart = null;

  const chordDiagrams = {
    'G': { frets: [3,2,0,0,0,3], fingers: [2,1,0,0,0,3], barres: [] },
    'D': { frets: ['x','x',0,2,3,2], fingers: [0,0,0,1,3,2], barres: [] },
    'Em': { frets: [0,2,2,0,0,0], fingers: [0,2,3,0,0,0], barres: [] },
    'C': { frets: ['x',3,2,0,1,0], fingers: [0,3,2,0,1,0], barres: [] },
    'Am': { frets: ['x',0,2,2,1,0], fingers: [0,0,2,3,1,0], barres: [] },
    'F': { frets: [1,3,3,2,1,1], fingers: [1,3,4,2,1,1], barres: [{fret:1, fromString:0, toString:5}] },
    'A': { frets: ['x',0,2,2,2,0], fingers: [0,0,1,1,1,0], barres: [] },
    'E': { frets: [0,2,2,1,0,0], fingers: [0,2,3,1,0,0], barres: [] },
    'F#m': { frets: [2,4,4,2,2,2], fingers: [1,3,4,1,1,1], barres: [{fret:2, fromString:0, toString:5}] }
  };

  function esc(str) {
    return (str || '').toString().replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function statusLabel(status) {
    const map = {
      'not_started': '🔴 Não comecei',
      'learning': '🟠 Estou aprendendo',
      'slow': '🟡 Consigo tocar devagar',
      'mastered': '🟢 Consigo tocar inteira',
      'dominant': '⭐ Dominada'
    };
    return map[status] || status;
  }

  async function loadJSON(url) {
    const res = await fetch(url, {cache: 'no-store'});
    if (!res.ok) throw new Error(url + ' ' + res.status);
    return res.json();
  }

  function renderSongList() {
    const container = document.getElementById('song-list');
    if (!container) return;
    container.innerHTML = playlist.map(song => {
      const active = currentSong && currentSong.id === song.id ? 'active' : '';
      return `
        <div class="song-item ${active}" data-id="${esc(song.id)}">
          <div class="song-title">${esc(song.title)}</div>
          <div class="song-artist">${esc(song.artist)}</div>
          <div class="song-status">${statusLabel(song.status)}</div>
        </div>
      `;
    }).join('');

    container.querySelectorAll('.song-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = item.getAttribute('data-id');
        const song = playlist.find(s => s.id === id);
        if (song) selectSong(song);
      });
    });
  }

  function selectSong(song) {
    currentSong = song;
    renderSongList();
    document.getElementById('song-title').textContent = song.title;
    document.getElementById('song-artist').textContent = song.artist;
    document.getElementById('song-bpm').textContent = `${song.bpm || '--'} BPM`;
    document.getElementById('song-key').textContent = `TOM: ${song.key || '--'}`;
    document.getElementById('song-tuning').textContent = `AFINAÇÃO: ${song.tuning || '--'}`;
    document.getElementById('song-difficulty').textContent = song.difficulty || '--';
    originalBpm = song.bpm || null;
    adjustedBpm = originalBpm;

    const embed = document.getElementById('youtube-embed');
    if (song.youtube_url && song.youtube_url.includes('watch')) {
      const videoId = song.youtube_url.split('v=')[1]?.split('&')[0];
      if (videoId) {
        embed.src = `https://www.youtube.com/embed/${videoId}?enablejsapi=1`;
        document.getElementById('no-audio-msg').classList.add('hidden');
        embed.classList.remove('hidden');
      }
    } else {
      embed.classList.add('hidden');
      document.getElementById('no-audio-msg').classList.remove('hidden');
    }

    renderTeleprompter(song);
    renderStructure(song);
    renderGuitarModes(song);
    loadProgress(song);
  }

  function renderTeleprompter(song) {
    const container = document.getElementById('tele-content');
    if (!container || !song.sections) return;
    let html = '';
    for (const section of song.sections) {
      html += `<div class="tele-section"><div class="section-label">${esc(section.name)}</div>`;
      for (const line of section.lines) {
        html += `<div class="tele-line" data-time="${line.time}" data-chord="${esc(line.chord)}"><span class="chord">${esc(line.chord)}</span>${esc(line.text)}</div>`;
      }
      html += '</div>';
    }
    container.innerHTML = html;
    container.style.fontSize = fontSize + 'px';
  }

  function renderStructure(song) {
    const container = document.getElementById('structure-timeline');
    if (!container || !song.sections) return;
    container.innerHTML = song.sections.map(section =>
      `<button class="structure-btn" data-start="${section.start}" data-end="${section.end}">${esc(section.name)}</button>`
    ).join('');

    container.querySelectorAll('.structure-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const start = parseFloat(btn.getAttribute('data-start'));
        if (!isNaN(start) && audioEl) {
          audioEl.currentTime = start;
          if (!isPlaying) togglePlay();
        }
      });
    });
  }

  function renderGuitarModes(song) {
    renderChordView(song);
    renderTabView(song);
    renderDiagramGrid(song);
    renderNotesView(song);
    renderSimpleView(song);
  }

  function renderChordView(song) {
    const container = document.getElementById('chord-view');
    if (!container || !song.sections) return;
    const orderedChords = song.sections.flatMap(section =>
      section.lines.map(line => ({ chord: line.chord, section: section.name, time: line.time }))
    );
    const unique = [];
    const seen = new Set();
    for (const item of orderedChords) {
      if (!seen.has(item.chord)) {
        seen.add(item.chord);
        unique.push(item);
      }
    }
    container.innerHTML = unique.map(item => {
      const diag = chordDiagrams[item.chord] || chordDiagrams['G'];
      return `
        <div class="chord-card" data-chord="${esc(item.chord)}">
          <div class="chord-name">${esc(item.chord)} <span class="chord-meta">${esc(item.section)}</span></div>
          <div class="chord-svg-wrap">
            <svg class="chord-svg" viewBox="0 0 100 110">
              ${renderChordSVG(diag)}
            </svg>
          </div>
          <div class="chord-fingering">
            ${diag.frets.map((fret, idx) => `<span>${fret === 'x' ? '×' : fret}</span>`).join('')}
          </div>
        </div>
      `;
    }).join('');
  }

  function renderChordSVG(diag) {
    const strings = 6;
    const frets = 5;
    const startX = 10;
    const startY = 22;
    const width = 80;
    const height = 80;
    const stringSpacing = width / (strings - 1);
    const fretSpacing = height / frets;
    let svg = '';

    // nut
    svg += `<line x1="${startX}" y1="${startY}" x2="${startX + width}" y2="${startY}" stroke="#c8e86b" stroke-width="2" />`;

    // string labels E A D G B e
    const stringLabels = ['E', 'A', 'D', 'G', 'B', 'e'];
    for (let i = 0; i < strings; i++) {
      const x = startX + i * stringSpacing;
      svg += `<text x="${x}" y="${startY - 5}" fill="#8aa3b8" font-size="9" text-anchor="middle">${stringLabels[i]}</text>`;
    }

    // frets
    for (let i = 1; i <= frets; i++) {
      const y = startY + i * fretSpacing;
      svg += `<line x1="${startX}" y1="${y}" x2="${startX + width}" y2="${y}" stroke="#2f4055" stroke-width="1" />`;
    }

    // strings
    for (let i = 0; i < strings; i++) {
      const x = startX + i * stringSpacing;
      svg += `<line x1="${x}" y1="${startY}" x2="${x}" y2="${startY + height}" stroke="#8aa3b8" stroke-width="1" />`;
    }

    // finger positions
    for (let string = 0; string < strings; string++) {
      const fret = diag.frets[string];
      const x = startX + string * stringSpacing;
      if (fret === 'x') {
        svg += `<text x="${x}" y="${startY - 2}" fill="#ff5f6d" font-size="10" text-anchor="middle">×</text>`;
        continue;
      }
      const y = startY + (fret - 0.5) * fretSpacing;
      svg += `<circle cx="${x}" cy="${y}" r="4" fill="#c8e86b" />`;
      svg += `<text x="${x}" y="${y + 14}" fill="#8aa3b8" font-size="8" text-anchor="middle">${diag.fingers[string]}</text>`;
    }

    // fret numbers
    for (let i = 1; i <= frets; i++) {
      const y = startY + i * fretSpacing;
      svg += `<text x="${startX - 4}" y="${y + 3}" fill="#8aa3b8" font-size="8" text-anchor="end">${i}</text>`;
    }

    return svg;
  }

  function renderTabView(song) {
    const container = document.getElementById('tab-view');
    if (!container || !song.sections) return;
    const measures = 16;
    const rows = ['e|', 'B|', 'G|', 'D|', 'A|', 'E|'];
    const sep = '-'.repeat(measures * 2);
    let tab = rows.map(r => `${r}${sep}`).join('\n');

    for (const section of song.sections) {
      tab += `\n[${section.name}]\n`;
      const chord = section.lines[0]?.chord || '';
      const text = section.lines.map(l => l.text).join(' / ');
      tab += `${chord} | ${text}\n`;
      tab += `${' '.repeat(Math.max(0, measures * 2 - 6))} |\n`;
    }
    container.textContent = tab;
  }

  function renderDiagramGrid(song) {
    const container = document.getElementById('diagram-grid');
    if (!container || !song.sections) return;
    const chords = [...new Set(song.sections.flatMap(s => s.lines.map(l => l.chord)))];
    container.innerHTML = chords.map(chord => {
      const diag = chordDiagrams[chord] || chordDiagrams['G'];
      return `
        <div class="chord-card">
          <div class="chord-name">${esc(chord)}</div>
          <svg class="chord-svg" viewBox="0 0 100 110">
            ${renderChordSVG(diag)}
          </svg>
        </div>
      `;
    }).join('');
  }

  function renderNotesView(song) {
    const container = document.getElementById('notes-view');
    if (!container || !song.sections) return;
    const uniqueChords = [...new Set(song.sections.flatMap(s => s.lines.map(l => l.chord)))];
    const notes = [
      `BPM: ${song.bpm || '--'}`,
      `TOM: ${song.key || '--'}`,
      `AFINAÇÃO: ${song.tuning || 'Standard'}`,
      `DIFICULDADE: ${song.difficulty || '--'}`,
      `CIFRAS: ${uniqueChords.join(', ') || '--'}`
    ].join('\n');
    container.textContent = `ANÁLISE\n${'='.repeat(40)}\n\n${notes}`;
  }

  function renderSimpleView(song) {
    const container = document.getElementById('simple-view');
    if (!container || !song.sections) return;
    const simpleMap = { 'G': 'C', 'Em': 'C', 'C': 'G', 'Am': 'F', 'D': 'G' };
    const simplified = song.sections.map(section => {
      return section.lines.map(line => ({
        ...line,
        simple: simpleMap[line.chord] || line.chord
      }));
    });
    let html = '';
    for (const section of simplified) {
      const name = song.sections.find(s => s.lines.includes(section[0]))?.name || '';
      html += `<div class="simple-card"><strong>${esc(name)}</strong><br/>`;
      for (const line of section) {
        html += `<div><span class="simple-chord">${esc(line.simple)}</span> — ${esc(line.text)}</div>`;
      }
      html += '</div>';
    }
    container.innerHTML = html;
  }

  function updateTeleprompter() {
    if (!currentSong || !audioEl || !teleAuto) return;
    const time = audioEl.currentTime;
    const lines = document.querySelectorAll('.tele-line');
    let activeLine = null;
    let prevChord = null;
    let nextChord = null;

    const timeOrdered = Array.from(lines).filter(line => {
      const t = parseFloat(line.getAttribute('data-time'));
      return !isNaN(t);
    }).sort((a, b) => parseFloat(a.getAttribute('data-time')) - parseFloat(b.getAttribute('data-time')));

    for (const line of timeOrdered) {
      const lineTime = parseFloat(line.getAttribute('data-time'));
      if (lineTime <= time) {
        activeLine = line;
        prevChord = line.getAttribute('data-chord');
      } else {
        if (!nextChord) nextChord = line.getAttribute('data-chord');
      }
    }

    lines.forEach(l => l.classList.remove('active'));

    if (activeLine) {
      activeLine.classList.add('active');
      activeLine.scrollIntoView({behavior: 'smooth', block: 'center'});
    }

    const chordIndicator = document.getElementById('chord-indicator');
    if (chordIndicator) {
      const current = activeLine?.getAttribute('data-chord') || '--';
      chordIndicator.textContent = `Acorde: ${current}` + (prevChord ? ` | Anterior: ${prevChord}` : '') + (nextChord ? ` | Próximo: ${nextChord}` : '');
    }

    document.querySelectorAll('.chord-card').forEach(card => card.classList.remove('active-chord'));
    const currentChord = activeLine?.getAttribute('data-chord');
    if (currentChord) {
      document.querySelectorAll(`.chord-card[data-chord="${esc(currentChord)}"]`).forEach(card => card.classList.add('active-chord'));
    }
  }

  function togglePlay() {
    if (!audioEl) return;
    if (isPlaying) {
      audioEl.pause();
      isPlaying = false;
      stopPracticeTimer();
    } else {
      audioEl.play().catch(() => {});
      isPlaying = true;
      startPracticeTimer();
    }
    updatePlayButton();
  }

  function updatePlayButton() {
    const btn = document.getElementById('btn-play');
    if (btn) btn.textContent = isPlaying ? '▶ PLAY' : '▶ PLAY';
  }

  function startPracticeTimer() {
    practiceStart = Date.now();
    practiceTimer = setInterval(() => {
      if (currentSong && practiceStart) {
        const minutes = Math.floor((Date.now() - practiceStart) / 60000);
        const el = document.getElementById('practice-live');
        if (el) el.textContent = `${minutes} min`;
      }
    }, 1000);
  }

  function stopPracticeTimer() {
    if (practiceTimer) clearInterval(practiceTimer);
    practiceTimer = null;
  }

  function setPlaybackRate(rate) {
    playbackRate = rate;
    if (audioEl) audioEl.playbackRate = rate;
    document.querySelectorAll('.speed').forEach(btn => {
      btn.classList.toggle('active', parseFloat(btn.getAttribute('data-speed')) === rate);
    });
  }

  function adjustBpm(delta) {
    if (!originalBpm) return;
    adjustedBpm = Math.max(40, Math.min(240, (adjustedBpm || originalBpm) + delta));
    const ratio = adjustedBpm / originalBpm;
    setPlaybackRate(Math.round(ratio * 100) / 100);
    const bpmDisplay = document.getElementById('song-bpm');
    if (bpmDisplay) bpmDisplay.textContent = `${adjustedBpm} BPM`;
  }

  function toggleLoop() {
    loopEnabled = !loopEnabled;
    const btn = document.getElementById('btn-loop');
    if (btn) btn.textContent = loopEnabled ? '🔁 LOOP ON' : '🔁 LOOP A→B';
    if (audioEl) audioEl.loop = loopEnabled;
  }

  function loadProgress(song) {
    const statusEl = document.getElementById('progress-status');
    const bpmEl = document.getElementById('progress-bpm');
    const minutesEl = document.getElementById('progress-minutes');
    const sectionsEl = document.getElementById('progress-sections');
    const difficultEl = document.getElementById('progress-difficult');
    if (statusEl) statusEl.value = song.status || 'not_started';
    if (bpmEl) bpmEl.value = song.max_bpm || 0;
    if (minutesEl) minutesEl.value = song.practice_minutes || 0;
    if (sectionsEl) sectionsEl.value = (song.mastered_sections || []).join(', ');
    if (difficultEl) difficultEl.value = song.difficult_parts || '';
  }

  async function saveProgress() {
    if (!currentSong) return;
    const status = document.getElementById('progress-status')?.value || 'not_started';
    const maxBpm = parseInt(document.getElementById('progress-bpm')?.value || '0', 10);
    const minutes = parseInt(document.getElementById('progress-minutes')?.value || '0', 10);
    const sections = document.getElementById('progress-sections')?.value || '';
    const difficult = document.getElementById('progress-difficult')?.value || '';

    currentSong.status = status;
    currentSong.max_bpm = maxBpm;
    currentSong.practice_minutes = minutes;
    currentSong.mastered_sections = sections.split(',').map(s => s.trim()).filter(Boolean);
    currentSong.difficult_parts = difficult;
    currentSong.last_practice = new Date().toISOString();

    try {
      const res = await fetch(`${SONG_BASE}${currentSong.id}.json`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(currentSong)});
      if (res.ok) {
        alert('Progresso salvo com sucesso!');
        renderSongList();
      } else {
        alert('Falha ao salvar progresso.');
      }
    } catch (e) {
      alert('Falha ao salvar progresso: ' + e.message);
    }
  }

  function updateCounts() {
    const total = playlist.length;
    const mastered = playlist.filter(s => s.status === 'mastered' || s.status === 'dominant').length;
    const learning = playlist.filter(s => s.status === 'learning' || s.status === 'slow').length;
    const minutes = playlist.reduce((sum, s) => sum + (s.practice_minutes || 0), 0);
    const countSongs = document.getElementById('count-songs');
    const countMastered = document.getElementById('count-mastered');
    const countLearning = document.getElementById('count-learning');
    const countTime = document.getElementById('count-time');
    if (countSongs) countSongs.textContent = total;
    if (countMastered) countMastered.textContent = mastered;
    if (countLearning) countLearning.textContent = learning;
    if (countTime) countTime.textContent = minutes;
  }

  async function init() {
    console.log('init start');
    let detailMap = {};
    try {
      console.log('Loading detail playlist from', SONG_BASE + 'playlist-' + PLAYLIST_ID + '.json');
      const rawPlaylist = await loadJSON(SONG_BASE + 'playlist-' + PLAYLIST_ID + '.json');
      const detailArr = Array.isArray(rawPlaylist) ? rawPlaylist : (rawPlaylist.items || []);
      detailMap = detailArr.reduce((acc, item) => { if (item && item.id) acc[item.id] = item; return acc; }, {});
      console.log('detailMap loaded:', Object.keys(detailMap).length);
    } catch (e) {
      console.warn('Detailed playlist not loaded:', e);
    }
    try {
      console.log('Loading index playlist from', PLAYLIST_URL);
      const raw = await loadJSON(PLAYLIST_URL);
      const indexItems = Array.isArray(raw) ? raw : (raw.items || []);
      const mapped = indexItems.map(item => ({ ...(detailMap[item.id] || {}), ...item }));
      console.log('mapped playlist:', mapped.length);
      playlist = mapped.filter(Boolean);
      console.log('final playlist:', playlist.length);
    } catch (e) {
      console.error('Failed to load repertoire:', e);
      document.querySelector('.sidebar').innerHTML = '<div class="card">Falha ao carregar repertório: ' + esc(e.message) + '</div>';
      return;
    }
    renderSongList();
    updateCounts();

    // Audio element for local upload
    audioEl = new Audio();
    audioEl.addEventListener('timeupdate', () => {
      const current = document.getElementById('time-current');
      const total = document.getElementById('time-total');
      if (current) current.textContent = formatTime(audioEl.currentTime);
      if (total) total.textContent = formatTime(audioEl.duration);
      updateTeleprompter();
      if (loopEnabled && loopB && audioEl.currentTime >= loopB) {
        audioEl.currentTime = loopA || 0;
      }
    });

    document.getElementById('btn-play').addEventListener('click', togglePlay);
    document.getElementById('btn-pause').addEventListener('click', () => {
      if (audioEl) { audioEl.pause(); isPlaying = false; stopPracticeTimer(); updatePlayButton(); }
    });
    document.getElementById('btn-loop').addEventListener('click', toggleLoop);
    document.getElementById('btn-restart').addEventListener('click', () => {
      if (audioEl) { audioEl.currentTime = 0; }
    });

    document.querySelectorAll('.speed').forEach(btn => {
      btn.addEventListener('click', () => setPlaybackRate(parseFloat(btn.getAttribute('data-speed'))));
    });

    document.getElementById('bpm-minus5').addEventListener('click', () => adjustBpm(-5));
    document.getElementById('bpm-minus1').addEventListener('click', () => adjustBpm(-1));
    document.getElementById('bpm-original').addEventListener('click', () => {
      if (originalBpm) {
        adjustedBpm = originalBpm;
        setPlaybackRate(1.0);
        document.getElementById('song-bpm').textContent = `${originalBpm} BPM`;
      }
    });
    document.getElementById('bpm-plus1').addEventListener('click', () => adjustBpm(1));
    document.getElementById('bpm-plus5').addEventListener('click', () => adjustBpm(5));

    document.getElementById('btn-tele-auto').addEventListener('click', () => {
      teleAuto = !teleAuto;
      document.getElementById('btn-tele-auto').textContent = `AUTO: ${teleAuto ? 'ON' : 'OFF'}`;
    });
    document.getElementById('btn-tele-font').addEventListener('click', () => {
      fontSize = fontSize === 22 ? 28 : fontSize === 28 ? 34 : 22;
      document.getElementById('tele-content').style.fontSize = fontSize + 'px';
    });
    document.getElementById('btn-tele-dark').addEventListener('click', () => {
      darkMode = !darkMode;
      document.body.style.background = darkMode ? '#0b0f14' : '#f4f6f9';
      document.body.style.color = darkMode ? '#e6eef7' : '#111820';
    });
    document.getElementById('btn-tele-full').addEventListener('click', () => {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        document.documentElement.requestFullscreen();
      }
    });

    document.querySelectorAll('.mode-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.mode-section').forEach(s => s.classList.remove('active'));
        tab.classList.add('active');
        const mode = tab.getAttribute('data-mode');
        const panel = document.getElementById(`mode-${mode}`);
        if (panel) panel.classList.add('active');
      });
    });

    document.querySelectorAll('.btn.print').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.getAttribute('data-print');
        const panelMap = { chord: 'mode-chord', tab: 'mode-tab', diagram: 'mode-diagram' };
        const panelId = panelMap[target];
        if (!panelId) return;
        const panel = document.getElementById(panelId);
        if (!panel) return;
        document.querySelectorAll('.mode-section').forEach(s => s.classList.remove('active', 'printing'));
        panel.classList.add('active', 'printing');
        setTimeout(() => window.print(), 60);
      });
    });

    document.getElementById('btn-save-progress').addEventListener('click', saveProgress);

    document.getElementById('audio-upload').addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file && audioEl) {
        audioEl.src = URL.createObjectURL(file);
        audioEl.load();
      }
    });

    const first = playlist[0];
    if (first) selectSong(first);
  }

  init();
})();
