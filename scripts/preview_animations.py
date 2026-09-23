"""Render animation review sheets and an offline animated preview; no build required."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from mikan_pet.core.animation_frames import FRAME_INTERVAL_MS
from mikan_pet.core.sprites import SKINS, frame_count, rasterize_frame
from mikan_pet.core.types import Direction, Pose, SkinId


def render(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    poses = list(Pose)[4:]
    data = {}
    for skin in SkinId:
        sheet = Image.new('RGB', (110 + max(frame_count(pose) for pose in poses) * 140, len(poses) * 144), '#eee8dc')
        draw = ImageDraw.Draw(sheet)
        data[skin.value] = {}
        for row, pose in enumerate(poses):
            draw.text((8, row * 144 + 55), pose.value, fill='#40352c')
            frames = []
            for index in range(frame_count(pose)):
                pixels = rasterize_frame(skin, pose, index, Direction.RIGHT)
                frames.append(pixels)
                tile = Image.new('RGBA', (32, 32))
                for y, line in enumerate(pixels):
                    for x, color in enumerate(line):
                        if color:
                            tile.putpixel((x, y), (*bytes.fromhex(color[1:]), 255))
                tile = tile.resize((128, 128), Image.Resampling.NEAREST)
                sheet.paste(tile, (110 + index * 140, row * 144), tile)
            data[skin.value][pose.value] = frames
        sheet.save(output / f'{skin.value}-frames.png')
    template = '''<!doctype html><html lang="id"><meta charset="utf-8">
<title>Mikan Pet - Pratinjau animasi</title>
<style>
body{margin:32px;background:#eee8dc;color:#40352c;font:16px system-ui}
h1{font-size:26px;margin-bottom:8px}button,select{font:inherit;padding:8px 12px;border:1px solid #b6a990;border-radius:8px;background:#fff8ed}
.tools{display:flex;gap:12px;align-items:center;margin:24px 0;flex-wrap:wrap}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;max-width:1150px}
article{background:#fff8ed;border:1px solid #dbcfbb;border-radius:14px;padding:16px;text-align:center}
canvas{width:160px;height:160px;image-rendering:pixelated}h2{font-size:16px;margin:4px}
p{max-width:850px;line-height:1.5}small{color:#6d604c}
</style><h1>Mikan Pet · Gerakan baru</h1>
<p>Pratinjau frame dari kode aplikasi. Pilih skin dan arah untuk memeriksa bentuk kucing. Semua gerakan memakai palet asli dan kanvas 32 × 32 piksel.</p>
<div class="tools"><label>Skin <select id="skin">OPTIONS</select></label>
<label>Arah <select id="direction"><option value="right">Kanan</option><option value="left">Kiri</option></select></label>
<button id="pause">Jeda</button><button id="step">Frame berikutnya</button></div><main id="gallery"></main>
<p><small>Diangkat: badan mengikuti arah drag dan kembali netral saat kursor berhenti. Mengangguk: merespons status pemutaran, bukan deteksi ketukan audio. Pratinjau ini mengulang setiap gerakan agar mudah diperiksa.</small></p>
<script>
const data=DATA, timing=TIMING;
const gallery=document.getElementById('gallery'), skin=document.getElementById('skin'), direction=document.getElementById('direction'), pause=document.getElementById('pause'), step=document.getElementById('step');
const labels={groom:'Membersihkan wajah',stretch:'Meregangkan badan',scratch:'Menggaruk telinga',tail:'Ekor & telinga',look:'Mengikuti kursor',jump:'Lompatan senang',music:'Mengangguk saat musik',yawn:'Menguap',sit:'Duduk melihat sekitar',play:'Bermain bola benang',carried:'Diangkat & bergoyang',land:'Mendarat'};
let paused=false;
const cards=Object.keys(labels).map(pose=>{const article=document.createElement('article');article.innerHTML='<h2>'+labels[pose]+'</h2><canvas width="32" height="32"></canvas><div><small></small></div>';gallery.append(article);return {pose,elapsed:0,ctx:article.querySelector('canvas').getContext('2d'),caption:article.querySelector('small')}});
function draw(){for(const {pose,elapsed,ctx,caption} of cards){const frames=data[skin.value][pose],n=Math.floor(elapsed/timing[pose])%frames.length;ctx.clearRect(0,0,32,32);frames[n].forEach((row,y)=>row.forEach((color,x)=>{if(color){ctx.fillStyle=color;ctx.fillRect(direction.value==='left'?31-x:x,y,1,1)}}));caption.textContent='Frame '+(n+1)+' / '+frames.length+' · '+timing[pose]+' ms'}}
pause.onclick=()=>{paused=!paused;pause.textContent=paused?'Putar':'Jeda'};
step.onclick=()=>{paused=true;pause.textContent='Putar';for(const card of cards){const ms=timing[card.pose];card.elapsed+=ms-card.elapsed%ms}draw()};
skin.onchange=direction.onchange=draw;setInterval(()=>{if(!paused){for(const card of cards)card.elapsed+=30;draw()}},30);draw();
</script></html>'''
    options = ''.join(f'<option value="{skin.value}">{SKINS[skin].display_name}</option>' for skin in SkinId)
    (output / 'index.html').write_text(template.replace('OPTIONS', options).replace('DATA', json.dumps(data)).replace('TIMING', json.dumps({pose.value: FRAME_INTERVAL_MS[pose] for pose in poses})), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    render(parser.parse_args().output)
