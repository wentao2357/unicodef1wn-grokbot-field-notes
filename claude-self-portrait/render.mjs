#!/usr/bin/env node
// Renders portrait.html to a video (or to stills) with headless Chromium and ffmpeg.
//
//   npm install
//   node render.mjs                              # → claude-self-portrait.mp4
//   node render.mjs --still 20,61.5              # → stills/t020.00.png, stills/t061.50.png
//   node render.mjs --from 50 --to 70 --out preview.mp4
//
// Every frame is a pure function of time, so frames are split across several
// browser pages and encoded once at the end.

import { chromium } from 'playwright';
import ffmpegStatic from 'ffmpeg-static';
import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FFMPEG = process.env.FFMPEG || ffmpegStatic || 'ffmpeg';
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.woff2': 'font/woff2' };

const USAGE = `usage: node render.mjs [options]
  --fps N            frames per second (default 30)
  --crf N            x264 quality, lower is better (default 20)
  --workers N        parallel browser pages (default: CPU count, max 6)
  --from S --to S    render only part of the piece (seconds)
  --out FILE         output video (default claude-self-portrait.mp4)
  --no-audio         leave out the soundtrack
  --still T1,T2,...  write PNG stills at these times instead of a video
  --stills-dir DIR   where stills go (default ./stills)
  --frames-dir DIR   keep intermediate PNG frames here
  --timeline         print the timeline (named moments, in seconds) and exit`;

function parseArgs(argv) {
  const a = { fps: 30, crf: 20, workers: Math.max(1, Math.min(6, os.cpus().length)), out: 'claude-self-portrait.mp4', audio: true };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i], v = () => argv[++i];
    if (k === '--fps') a.fps = +v();
    else if (k === '--crf') a.crf = +v();
    else if (k === '--workers') a.workers = +v();
    else if (k === '--from') a.from = +v();
    else if (k === '--to') a.to = +v();
    else if (k === '--out') a.out = v();
    else if (k === '--no-audio') a.audio = false;
    else if (k === '--still') a.still = v().split(',').map(Number);
    else if (k === '--stills-dir') a.stillsDir = v();
    else if (k === '--frames-dir') a.framesDir = v();
    else if (k === '--timeline') a.timeline = true;
    else if (k === '--help' || k === '-h') { console.log(USAGE); process.exit(0); }
    else throw new Error(`unknown option ${k}\n${USAGE}`);
  }
  return a;
}

// Serves this folder, and accepts rendered frames, stills and audio by POST.
function serve(sink) {
  const server = http.createServer((req, res) => {
    const url = decodeURIComponent(req.url.split('?')[0]);
    if (req.method === 'POST') {
      const target = sink(url);
      if (!target) return res.writeHead(404).end();
      const chunks = [];
      req.on('data', c => chunks.push(c));
      req.on('end', () => {
        fs.writeFileSync(target, Buffer.concat(chunks));
        res.end('ok');
      });
      return;
    }
    const file = path.join(HERE, path.normalize(url === '/' ? '/portrait.html' : url));
    if (!file.startsWith(HERE) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return res.writeHead(404).end();
    res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server)));
}

function ffmpeg(args) {
  const r = spawnSync(FFMPEG, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) throw new Error(`ffmpeg failed:\n${r.stderr}`);
  return r.stderr;
}

// Linear gain that brings the soundtrack to the target loudness without clipping.
function loudnessGain(wav, target = -19, ceiling = -1.5) {
  const log = ffmpeg(['-hide_banner', '-nostats', '-i', wav, '-af', `loudnorm=I=${target}:TP=${ceiling}:LRA=11:print_format=json`, '-f', 'null', '-']);
  const m = JSON.parse(log.slice(log.lastIndexOf('{'), log.lastIndexOf('}') + 1));
  const I = parseFloat(m.input_i), TP = parseFloat(m.input_tp);
  const gain = Math.min(target - I, ceiling - TP);
  return { I, TP, gain };
}

const args = parseArgs(process.argv.slice(2));
const framesDir = args.framesDir ? path.resolve(args.framesDir) : fs.mkdtempSync(path.join(os.tmpdir(), 'portrait-'));
const stillsDir = path.resolve(args.stillsDir || path.join(HERE, 'stills'));
fs.mkdirSync(framesDir, { recursive: true });
let written = 0;

const server = await serve(url => {
  let m;
  if ((m = url.match(/^\/frame\/(\d+)$/))) { written++; return path.join(framesDir, `f${m[1].padStart(6, '0')}.png`); }
  if ((m = url.match(/^\/still\/([\w.-]+)$/))) return path.join(stillsDir, `${m[1]}.png`);
  if (url === '/audio') return path.join(framesDir, 'soundtrack.wav');
  return null;
});
const browser = await chromium.launch();

async function openPage() {
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('pageerror', e => console.error('[page error]', e.message));
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('[page]', m.text()); });
  await page.goto(`http://127.0.0.1:${server.address().port}/portrait.html?render`);
  await page.waitForFunction(() => window.portraitReady === true, null, { timeout: 120000 });
  return page;
}

try {
  if (args.timeline) {
    const page = await openPage();
    const tl = await page.evaluate(() => window.portrait.timeline);
    for (const [k, v] of Object.entries(tl)) if (typeof v === 'number') console.log(`${k.padEnd(9)} ${v.toFixed(2)}`);
  } else if (args.still) {
    fs.mkdirSync(stillsDir, { recursive: true });
    const page = await openPage();
    for (const t of args.still) {
      const name = `t${t.toFixed(2).padStart(6, '0')}`;
      await page.evaluate(([t, name]) => window.portrait.still(t, name), [t, name]);
      console.log(path.join(stillsDir, `${name}.png`));
    }
  } else {
    const pages = await Promise.all(Array.from({ length: args.workers }, openPage));
    const duration = await pages[0].evaluate(() => window.portrait.duration);
    const from = args.from ?? 0, to = Math.min(args.to ?? duration, duration);
    const first = Math.round(from * args.fps), last = Math.ceil(to * args.fps) - 1;
    const total = last - first + 1;
    console.log(`piece: ${duration.toFixed(2)} s · rendering ${total} frames at ${args.fps} fps with ${args.workers} workers`);

    let wav = null, gain = 0;
    if (args.audio) {
      await pages[0].evaluate(sr => window.portrait.soundtrack(sr), 48000);
      wav = path.join(framesDir, 'soundtrack.wav');
      const l = loudnessGain(wav);
      gain = l.gain;
      console.log(`soundtrack: ${l.I.toFixed(1)} LUFS, peak ${l.TP.toFixed(1)} dBTP → gain ${gain.toFixed(1)} dB`);
    }

    const started = Date.now();
    const timer = setInterval(() => {
      const s = (Date.now() - started) / 1000;
      console.log(`  ${written}/${total} frames · ${s.toFixed(0)} s · ${(written / s).toFixed(1)} fps`);
    }, 10000);
    await Promise.all(pages.map((page, w) => {
      const idx = [];
      for (let i = first + w; i <= last; i += args.workers) idx.push(i);
      return page.evaluate(([idx, fps]) => window.portrait.frames(idx, fps), [idx, args.fps]);
    }));
    clearInterval(timer);
    console.log(`frames done in ${((Date.now() - started) / 1000).toFixed(0)} s, encoding…`);

    const out = path.resolve(args.out);
    const ff = ['-y', '-hide_banner', '-loglevel', 'error',
      '-framerate', String(args.fps), '-start_number', String(first), '-i', path.join(framesDir, 'f%06d.png')];
    if (wav) ff.push('-ss', (first / args.fps).toFixed(4), '-t', (total / args.fps).toFixed(4), '-i', wav);
    ff.push('-map', '0:v', '-c:v', 'libx264', '-preset', 'slow', '-crf', String(args.crf), '-tune', 'animation',
      '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
      '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709');
    if (wav) ff.push('-map', '1:a', '-af', `volume=${gain.toFixed(2)}dB`, '-c:a', 'aac', '-b:a', '192k', '-shortest');
    ff.push('-movflags', '+faststart', out);
    ffmpeg(ff);
    console.log(`${out} · ${(fs.statSync(out).size / 1e6).toFixed(1)} MB`);
    if (!args.framesDir) fs.rmSync(framesDir, { recursive: true, force: true });
  }
} finally {
  await browser.close();
  server.close();
}
