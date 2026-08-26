# Painel de Treino de Repertório — Investigação e Arquitetura

Caso de teste: **Playlist YouTube "ENTREMUNDOS - 14/08 - SEXTA"** — João Marcos Coure
- Link: `https://youtube.com/playlist?list=PLa7WXH9S8Er8`
- Confirmado: 5 vídeos, perfil musical cristão/contemporâneo

---

## 1. É possível construir esse painel?
Sim. É um frontend-first com backend leve. O front cuida de teleprompter, player, diagramas, sincronização e telemetria de prática; o backend cuida de catálogo, scoring, sync de cifras/estrutura e histórico.

## 2. Ferramentas existentes
- Pesquisa musical/playlist: `yt-dlp` (CLI, JSON metadata, títulos/durações/captions sem baixar vídeo completo quando possível)
- Transcrição/alinhamento: `yt-dlp` com `--write-subs` / `--write-auto-subs` + pipeline de alinhamento com `whisper`/`faster-whisper`
- Detecção musical: `essentia`, `librosa`, `madmom` para BPM/tonalidade/segmentação
- MIDI/chord: `basic-pitch` (áudio→MIDI), `madmom`/`librosa` para chroma + detecção de acorde
- Time stretch/pitch shift legal: Web Audio API nativo (`AudioBufferSourceNode.playbackRate` muda pitch; para preservar pitch use pré-processamento offline: `librosa.effects.time_stretch` offline) e `soundtouch.js`/`wavesurfer.js` com plugin de velocidade
- Sincronização: `wavesurfer.js` + Regions/Timeline + hook de `audioprocess` ou `requestAnimationFrame`
- Notação/tablatura: `VexFlow`/`VexTab`
- Diagramas de acorde: `VexChords`, `chord-diagrams`, SVG próprio simples
- UI: React + nanostores + Tailwind + `framer-motion`/transições leves
- TUI alternativa: Ink (`react` no terminal via Hermes `--tui`) ou componente web minimalista

## 3. Skills instaláveis no OpenClaw
Sem referência a `OpenClaw` no repositório atual. Se for um runtime/externo, assuma: skills são módulos SOA com schema comum (goal/context/tools). Podemos construir skill de “repertoire ingestion” para:
- Ler playlist/URL
- Baixar/transcrever via `yt-dlp`
- Extrair BPM/tonalidade/estrutura
- Cruzar com catálogo de cifras/tabs
- Gerar o manifest do repertório

## 4. MCPs relevantes
Hoje não há MCPs nativos no repositório. Projeto futuramente pode expor:
- MCP de metadados musicais (YouTube/Spotify)
- MCP de MIR (`essentia`/`librosa`) via serviço local
- MCP de cifras/tabs (UltimateGuitar/Musescore/ChordPro públicas)
- MCP de prática/progresso (Redis/SQLite local)

## 5. APIs utilizáveis
- YouTube Data API v3: metadados públicos da playlist sem baixar áudio
- `yt-dlp`: extração legal e estável de títulos/durações/subtítulos
- `whisper.cpp`/`faster-whisper`: transcrição offline
- `Essentia`/`librosa`: extração musical offline
- **Importante:** áudio completo do YouTube pode não ser obtido sem violar ToS/direitos autorais. Usar apenas metadados públicos ou conteúdo autorizado.

## 6. Bibliotecas para usar
- Frontend player: `wavesurfer.js@7`
- Sincronização/teleprompter: Web Audio + `wavesurfer.js` Regions/Timeline
- Velocidade: Web Audio API + pré-processamento offline quando necessário para preservar pitch
- Notação/tab: `VexFlow`
- Diagramas de acorde: `VexChords` ou componente próprio SVG
- Estado: nanostores
- Backend ingest: `yt-dlp`, `faster-whisper`, `essentia`, `librosa`, `madmom`, `basic-pitch`
- Persistência local: SQLite/JSON já presente no projeto

## 7. O que desenvolver do zero
- Motor de sincronização cifra↔áudio por timestamp/section markers
- Teleprompter musical com autoavanço, retorno por seção, highlights e atalhos
- Modo performance minimalista
- Treino progressivo com BPM incremental e loop A→B
- Registro de progresso e métricas
- Integração do dashboard atual com módulo “Meu Repertório”
- Algoritmo de extração de estrutura musical (intro/verse/chorus/bridge/solo) via MIR heurística ou LLM-assisted sobre letra/durações

## 8. Como importar a playlist
Fluxo:
1. Salvar playlist em `data/playlists/<id>.json` com metadados públicos
2. Para cada vídeo, criar `data/repertoire/<slug>.json` com:
   - id, titulo, artista, url, duracao
   - source_meta, license_note
   - bpm, tom, estrutura, acordes, tabs, dificuldade
   - timestamps/regions, notas de estudo
3. Indexar em `data/scored_opportunities.json` ou novo `data/repertoire.json`

## 9. Transformar cada música em repertório
Entrada: URL/playlist
Processo:
- Normalizar título/artista
- Identificar BPM/tonalidade/duração
- Obter cifra oficial/alternativa de arquivos locais ou CifraClub/UltimateGuitar via scraping autorizado
- Gerar seções estimadas
- Gerar manifest com modos: [CIFRA][TAB][DIAGRAMA][NOTAS][SIMPLIFICADO]

## 10. Sincronizar cifra e áudio
- Se houver timestamps: marcações absolutas + Regions no `wavesurfer.js`
- Se houver estrutura: mapear seções com start/end
- Se houver letra/cifra com timestamps: teleprompter sincronizado
- Fallback: rolagem manual + avanço por seção

## 11. Criar o teleprompter
- Lista de linhas sincronizadas por tempo
- Destaque de linha atual e acorde atual
- Controles: autoscroll on/off, velocidade de rolagem, tamanho de fonte
- Atalhos: seção anterior/próxima, rewind 5s, loop A→B

## 12. Modo guitarra
- Renderizar nome do acorde + diagrama SVG acima da cifra
- Mostrar alternativa simplificada quando disponível
- Indicar acorde anterior/próximo para preparo de posição

## 13. Loop inteligente
- Usar `wavesurfer.js` Regions para A/B
- Controles: repetições, BPM alvo, step incremental
- Aplicar mudança gradual de velocidade entre repetições

## 14. Treinamento progressivo
- Sequência de fases com BPM alvo e número de repetições
- Histórico por música: tentativas, erros, BPM máximo atingido

## 15. Registrar progresso
Estrutura:
```json
{
  "song_id": "...",
  "status": "not_started|learning|slow|mastered|dominant",
  "practice_minutes": 0,
  "max_bpm": 0,
  "mastered_sections": [],
  "last_practice": ""
}
```

## 16. Aplicação completa
- Fase 1: painel web standalone com playlist local, player e teleprompter
- Fase 2: ingestão automática da playlist, extração musical básica e repertório
- Fase 3: dashboard integrado ao Job Intelligence com métricas e histórico
- Fase 4: modo performance + treino progressivo
- Fase 5: exportação/impressão de setlist e compartilhamento

---

## Limitações legais/técnicas
- Conteúdo do YouTube: respeitar ToS e direitos autorais
- Solução compatível: usar metadados públicos + conteúdo próprio (cifras/tabs autorizadas)
- Processamento offline de áudio só é legal sobre material que o usuário tem direito de usar
- Sugerir fluxo híbrido: o painel aceita áudio local ou streaming oficial embutido, sem reprodução/processamento não autorizado

---

## Próximos passos imediatos
1. Criar `docs/repertoire-panel/contract.md`
2. Criar `data/playlists/PLa7WXH9S8Er8.json`
3. Criar `data/repertoire/schema.json`
4. Criar estrutura inicial do dashboard em `dashboard/repertoire/`
