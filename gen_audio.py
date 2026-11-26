"""產生每日日文的發音檔（Microsoft 神經語音 ja-JP-NanamiNeural）。

用法：  python gen_audio.py          只補上還沒有的音檔
        python gen_audio.py --all    全部重新產生
需要：  python -m pip install edge-tts

檔名是文字內容的 FNV-1a 雜湊（與 index.html 的 audioKey() 相同），
所以新增單字後重跑一次即可，不會影響既有檔案。
"""
import asyncio, json, os, re, sys
import edge_tts

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "audio")
VOICE = "ja-JP-NanamiNeural"


def fnv1a(text: str) -> str:
    h = 0x811C9DC5
    for b in text.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def load_items():
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    def block(name):
        a = html.index(f"const {name} = [")
        b = html.index("\n];", a)
        return [json.loads(l.strip().rstrip(",")) for l in html[a:b].splitlines() if l.strip().startswith("[")]
    jobs = {}  # 檔名鍵（播放時的文字） -> (實際朗讀文字, 語速)
    for v in block("VOCAB"):
        jp, kana = v[0], v[1]
        jobs[jp] = (kana or jp, "-10%")          # 單字用讀音朗讀，避免漢字被唸錯
        if len(v) > 3 and v[3]:
            jobs[v[3]] = (v[3], "-5%")           # 例句
    for p in block("PHRASES"):
        jobs[p[0]] = (p[0], "-5%")
    return jobs


async def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = load_items()
    redo = "--all" in sys.argv
    todo = [(k, t, r) for k, (t, r) in jobs.items() if redo or not os.path.exists(os.path.join(OUT, fnv1a(k) + ".mp3"))]
    sem = asyncio.Semaphore(6)
    async def one(key, text, rate):
        async with sem:
            path = os.path.join(OUT, fnv1a(key) + ".mp3")
            for attempt in range(3):
                try:
                    await edge_tts.Communicate(text, VOICE, rate=rate).save(path)
                    return
                except Exception as e:
                    if attempt == 2:
                        print("失敗：", key, e)
    await asyncio.gather(*(one(*j) for j in todo))
    print(f"共 {len(jobs)} 段文字，本次產生 {len(todo)} 個音檔")


asyncio.run(main())
